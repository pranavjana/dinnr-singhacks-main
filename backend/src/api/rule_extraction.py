"""
FastAPI endpoints for rule extraction workflow.
Feature: 003-langgraph-rule-extraction
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Literal
import structlog
from workflows.rule_extraction import extract_rules_from_document, extract_rules_batch
from services.supabase_service import get_supabase_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/extraction", tags=["Rule Extraction"])


# Request/Response Models

class ExtractionRequest(BaseModel):
    """Request to extract rules from a single document."""
    document_id: str = Field(description="UUID of document to process")
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}$", description="Two-letter jurisdiction code")
    target_rule_types: list[str] | None = Field(
        default=None,
        description="Specific rule types to extract (default: all)"
    )
    max_retries: int = Field(default=3, ge=0, le=5)


class BatchExtractionRequest(BaseModel):
    """Request to extract rules from multiple documents."""
    document_ids: list[str] = Field(min_length=1, max_length=50, description="List of document UUIDs")
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}$")
    target_rule_types: list[str] | None = None


class ExtractionResponse(BaseModel):
    """Response from extraction workflow."""
    workflow_run_id: str
    document_id: str
    status: Literal["completed", "partial", "failed"]
    rules_created: int
    rules_updated: int
    avg_confidence: float
    total_tokens_used: int
    cost_usd: float
    errors: list[str]
    deduplication_summary: dict | None = None


class BatchExtractionResponse(BaseModel):
    """Response from batch extraction."""
    total_documents: int
    successful: int
    failed: int
    results: list[ExtractionResponse]


class RuleQueryParams(BaseModel):
    """Query parameters for fetching rules."""
    jurisdiction: str | None = None
    rule_type: str | None = None
    validation_status: Literal["pending", "validated", "rejected", "archived"] | None = None
    active_only: bool = True
    limit: int = Field(default=50, le=100)


# Endpoints

@router.post("/extract", response_model=ExtractionResponse)
async def extract_rules(request: ExtractionRequest):
    """
    Extract AML compliance rules from a single document.

    This endpoint triggers the LangGraph workflow that:
    1. Retrieves document chunks from Supabase
    2. Extracts structured facts using Groq Kimi K2
    3. Normalizes and deduplicates rules
    4. Persists to compliance_rules table

    Returns workflow execution results including created rules and metrics.
    """
    logger.info(
        "Received extraction request",
        document_id=request.document_id,
        jurisdiction=request.jurisdiction
    )

    try:
        # Execute workflow
        final_state = await extract_rules_from_document(
            document_id=request.document_id,
            jurisdiction=request.jurisdiction,
            target_rule_types=request.target_rule_types,
            max_retries=request.max_retries,
        )

        # Build response
        response = ExtractionResponse(
            workflow_run_id=final_state["workflow_run_id"],
            document_id=final_state["document_id"],
            status=final_state.get("status", "completed"),
            rules_created=len(final_state.get("rule_ids_created", [])),
            rules_updated=len(final_state.get("rule_ids_updated", [])),
            avg_confidence=final_state.get("analyser_confidence", 0.0),
            total_tokens_used=final_state.get("tokens_used", 0),
            cost_usd=final_state.get("cost_usd", 0.0),
            errors=final_state.get("analyser_errors", []),
            deduplication_summary=final_state.get("deduplication_summary"),
        )

        return response

    except Exception as e:
        logger.error("Extraction failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.post("/extract/batch", response_model=BatchExtractionResponse)
async def extract_rules_batch_endpoint(
    request: BatchExtractionRequest,
    background_tasks: BackgroundTasks
):
    """
    Extract rules from multiple documents in batch.

    Processes documents concurrently for better performance.
    For large batches (>10 documents), consider using background processing.
    """
    logger.info(
        "Received batch extraction request",
        num_documents=len(request.document_ids),
        jurisdiction=request.jurisdiction
    )

    try:
        # Execute batch workflow
        results = await extract_rules_batch(
            document_ids=request.document_ids,
            jurisdiction=request.jurisdiction,
            target_rule_types=request.target_rule_types,
        )

        # Convert to response format
        response_results = [
            ExtractionResponse(
                workflow_run_id=state["workflow_run_id"],
                document_id=state["document_id"],
                status=state.get("status", "completed"),
                rules_created=len(state.get("rule_ids_created", [])),
                rules_updated=len(state.get("rule_ids_updated", [])),
                avg_confidence=state.get("analyser_confidence", 0.0),
                total_tokens_used=state.get("tokens_used", 0),
                cost_usd=state.get("cost_usd", 0.0),
                errors=state.get("analyser_errors", []),
                deduplication_summary=state.get("deduplication_summary"),
            )
            for state in results
        ]

        successful = sum(1 for r in response_results if r.status == "completed")
        failed = len(response_results) - successful

        return BatchExtractionResponse(
            total_documents=len(request.document_ids),
            successful=successful,
            failed=failed,
            results=response_results,
        )

    except Exception as e:
        logger.error("Batch extraction failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch extraction failed: {str(e)}")


@router.get("/rules")
async def get_compliance_rules(
    jurisdiction: str | None = None,
    rule_type: str | None = None,
    validation_status: str | None = None,
    active_only: bool = True,
    limit: int = 50,
):
    """
    Query compliance rules with filters.

    Returns list of rules in formatted structure.
    """
    db = get_supabase_service()

    try:
        # Build query
        query = db.client.table("compliance_rules").select("*")

        if jurisdiction:
            query = query.eq("jurisdiction", jurisdiction)

        if rule_type:
            query = query.eq("rule_type", rule_type)

        if validation_status:
            query = query.eq("validation_status", validation_status)

        if active_only:
            query = query.eq("is_active", True)

        query = query.order("created_at", desc=True).limit(limit)

        # Execute
        import asyncio
        response = await asyncio.to_thread(query.execute)

        # Format rules according to desired structure
        formatted_rules = []
        for rule in response.data or []:
            rule_data = rule.get("rule_data", {})

            formatted_rule = {
                "id": rule["id"],
                "rule_type": rule["rule_type"],
                "jurisdiction": rule["jurisdiction"],
                "regulator": rule["regulator"],
                "applies_to": rule_data.get("applies_to", []),
                "rule_details": {k: v for k, v in rule_data.items() if k not in ["applies_to", "source_text", "page_reference", "confidence"]},
                "source_text": rule_data.get("source_text", ""),
                "extraction_confidence": rule["extraction_confidence"],
                "effective_date": rule.get("effective_date"),
                "circular_number": rule.get("circular_number"),
                "validation_status": rule["validation_status"]
            }
            formatted_rules.append(formatted_rule)

        return {
            "count": len(formatted_rules),
            "rules": formatted_rules
        }

    except Exception as e:
        logger.error("Failed to query rules", error=str(e))
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/rules/{rule_id}")
async def get_rule_by_id(rule_id: str):
    """
    Fetch a specific rule by ID with full details.
    """
    db = get_supabase_service()

    try:
        import asyncio
        response = await asyncio.to_thread(
            lambda: db.client.table("compliance_rules")
            .select("*")
            .eq("id", rule_id)
            .single()
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Rule not found")

        return response.data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch rule: {str(e)}")


@router.get("/metrics/recent")
async def get_recent_metrics(limit: int = 10):
    """
    Get recent extraction workflow metrics for monitoring.

    Returns aggregated metrics from extraction_metrics table.
    """
    db = get_supabase_service()

    try:
        import asyncio
        response = await asyncio.to_thread(
            lambda: db.client.table("extraction_metrics")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return {
            "count": len(response.data),
            "metrics": response.data or []
        }

    except Exception as e:
        logger.error("Failed to fetch metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {str(e)}")


@router.post("/rules/{rule_id}/validate")
async def validate_rule(rule_id: str, validated_by: str):
    """
    Mark a rule as validated (human-in-loop approval).

    Updates validation_status to 'validated' and records validator.
    """
    db = get_supabase_service()

    try:
        import asyncio
        from datetime import datetime

        await asyncio.to_thread(
            lambda: db.client.table("compliance_rules")
            .update({
                "validation_status": "validated",
                "validated_by": validated_by,
                "validated_at": datetime.utcnow().isoformat(),
            })
            .eq("id", rule_id)
            .execute()
        )

        logger.info("Rule validated", rule_id=rule_id, validated_by=validated_by)

        return {"status": "success", "rule_id": rule_id}

    except Exception as e:
        logger.error("Failed to validate rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint for extraction service."""
    return {
        "status": "healthy",
        "service": "rule_extraction",
        "version": "1.0.0"
    }
