"""
FastAPI endpoints for rule extraction workflow.
Feature: 003-langgraph-rule-extraction
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Literal, Any
from datetime import datetime
from uuid import uuid4
import structlog
from workflows.rule_extraction import extract_rules_from_document, extract_rules_batch
from services.supabase_service import get_supabase_service
from services.confidence_analyzer import analyze_low_confidence
from services.manual_rules_store import (
    list_manual_rules,
    save_manual_rule,
    get_manual_rule,
    update_manual_rule,
)

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


ValidationStatusLiteral = Literal["pending", "validated", "rejected", "archived"]


class ComplianceRuleCreateRequest(BaseModel):
    """Request payload for manually creating a compliance rule."""
    rule_type: str = Field(min_length=1, description="Rule category, e.g., 'threshold'")
    jurisdiction: str = Field(min_length=2, description="Jurisdiction code (e.g., 'SG')")
    regulator: str | None = Field(default=None, description="Regulator name or acronym")
    description: str | None = Field(default=None, description="Short description of the rule")
    source_text: str = Field(min_length=1, description="Canonical source text for the rule")
    applies_to: list[str] = Field(default_factory=list, description="Entities the rule applies to")
    rule_details: dict[str, Any] = Field(default_factory=dict, description="Structured rule payload")
    extraction_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    effective_date: str | None = None
    circular_number: str | None = None
    validation_status: ValidationStatusLiteral = "pending"
    is_active: bool = True


class ComplianceRuleUpdateRequest(BaseModel):
    """Request payload for updating a compliance rule."""
    rule_type: str | None = None
    jurisdiction: str | None = None
    regulator: str | None = None
    description: str | None = None
    source_text: str | None = None
    applies_to: list[str] | None = None
    rule_details: dict[str, Any] | None = None
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    effective_date: str | None = None
    circular_number: str | None = None
    validation_status: ValidationStatusLiteral | None = None
    is_active: bool | None = None


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
        def format_rule(record: dict[str, Any]) -> dict[str, Any]:
            rule_data = record.get("rule_data") or {}
            return {
                "id": record["id"],
                "rule_type": record.get("rule_type"),
                "description": record.get("description") or "",
                "jurisdiction": record.get("jurisdiction"),
                "regulator": record.get("regulator"),
                "applies_to": rule_data.get("applies_to", []),
                "rule_details": {
                    k: v
                    for k, v in rule_data.items()
                    if k not in ["applies_to", "source_text", "page_reference", "confidence"]
                },
                "source_text": rule_data.get("source_text", ""),
                "extraction_confidence": record.get("extraction_confidence", 0.0),
                "effective_date": record.get("effective_date"),
                "circular_number": record.get("circular_number"),
                "validation_status": record.get("validation_status", "pending"),
                "created_at": record.get("created_at"),
                "updated_at": record.get("updated_at"),
            }

        formatted_rules: list[dict[str, Any]] = []

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

        # Execute Supabase query
        import asyncio
        response = await asyncio.to_thread(query.execute)

        for rule in response.data or []:
            formatted_rules.append(format_rule(rule))

        # Merge manual rules
        manual_rules = list_manual_rules()
        for manual_rule in manual_rules:
            if jurisdiction and manual_rule.get("jurisdiction") != jurisdiction:
                continue
            if rule_type and manual_rule.get("rule_type") != rule_type:
                continue
            if validation_status and manual_rule.get("validation_status") != validation_status:
                continue
            if active_only and manual_rule.get("is_active") is False:
                continue
            formatted_rules.append(format_rule(manual_rule))

        # Sort combined rules by updated_at/created_at descending
        def _sort_key(rule: dict[str, Any]):
            return rule.get("updated_at") or rule.get("created_at") or ""

        formatted_rules.sort(key=_sort_key, reverse=True)

        if limit:
            formatted_rules = formatted_rules[:limit]

        return {
            "count": len(formatted_rules),
            "rules": formatted_rules
        }

    except Exception as e:
        logger.error("Failed to query rules", error=str(e))
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/rules", status_code=201)
async def create_compliance_rule_endpoint(request: ComplianceRuleCreateRequest):
    """
    Manually create a compliance rule entry.
    """
    db = get_supabase_service()

    def _clean_list(values: list[str]) -> list[str]:
        return [item.strip() for item in values if isinstance(item, str) and item.strip()]

    try:
        rule_type = request.rule_type.strip()
        jurisdiction = request.jurisdiction.strip().upper()
        regulator = request.regulator.strip() if isinstance(request.regulator, str) else None
        description = request.description.strip() if isinstance(request.description, str) else request.description
        source_text = request.source_text.strip()

        rule_data = dict(request.rule_details) if request.rule_details else {}
        rule_data["applies_to"] = _clean_list(request.applies_to)
        rule_data["source_text"] = source_text

        now_iso = datetime.utcnow().isoformat()
        payload = {
            "rule_type": rule_type,
            "jurisdiction": jurisdiction,
            "regulator": regulator,
            "description": description,
            "rule_data": rule_data,
            "extraction_confidence": request.extraction_confidence,
            "effective_date": request.effective_date,
            "circular_number": request.circular_number,
            "validation_status": request.validation_status,
            "is_active": request.is_active,
            "updated_at": now_iso,
        }

        # Preserve creation timestamp if Supabase handles it; otherwise set explicitly
        payload.setdefault("created_at", now_iso)

        if request.validation_status == "validated":
            payload.setdefault("validated_at", now_iso)

        rule_id = await db.create_compliance_rule(payload)
        if rule_id:
            logger.info("Compliance rule created via API", rule_id=rule_id, rule_type=request.rule_type)
            return {"status": "success", "rule_id": rule_id}

        fallback_id = save_manual_rule({**payload, "id": str(uuid4())})
        logger.info("Compliance rule stored locally", rule_id=fallback_id, rule_type=request.rule_type)
        return {"status": "success", "rule_id": fallback_id, "source": "manual-store"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create compliance rule via Supabase, falling back to local store", error=str(e))
        fallback_id = save_manual_rule({**payload, "id": str(uuid4())})
        return {"status": "success", "rule_id": fallback_id, "source": "manual-store"}


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
            manual_rule = get_manual_rule(rule_id)
            if manual_rule:
                return manual_rule
            raise HTTPException(status_code=404, detail="Rule not found")

        return response.data

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch rule: {str(e)}")


@router.put("/rules/{rule_id}")
async def update_compliance_rule_endpoint(rule_id: str, request: ComplianceRuleUpdateRequest):
    """
    Update an existing compliance rule entry.
    """
    db = get_supabase_service()

    def _clean_list(values: list[str]) -> list[str]:
        return [item.strip() for item in values if isinstance(item, str) and item.strip()]

    manual_rule = get_manual_rule(rule_id)
    is_manual_rule = manual_rule is not None
    existing_record: dict[str, Any] | None = manual_rule

    if not is_manual_rule:
        try:
            import asyncio

            existing_response = await asyncio.to_thread(
                lambda: db.client.table("compliance_rules")
                .select("*")
                .eq("id", rule_id)
                .single()
                .execute()
            )

            existing_record = existing_response.data
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to fetch rule from Supabase", rule_id=rule_id, error=str(e))
            existing_record = None

    if not existing_record:
        raise HTTPException(status_code=404, detail="Rule not found")

    try:
        existing_rule_data = existing_record.get("rule_data") or {}
        rule_data = dict(existing_rule_data)
        rule_data_changed = False

        if request.rule_details is not None:
            # Preserve meta fields we manage separately
            preserved_meta = {
                key: value
                for key, value in existing_rule_data.items()
                if key in {"applies_to", "source_text", "page_reference", "confidence"}
            }
            rule_data = dict(request.rule_details)
            rule_data.update(preserved_meta)
            rule_data_changed = True

        if request.applies_to is not None:
            rule_data["applies_to"] = _clean_list(request.applies_to)
            rule_data_changed = True

        if request.source_text is not None:
            rule_data["source_text"] = request.source_text
            rule_data_changed = True

        updates: dict[str, Any] = {}

        if request.rule_type is not None:
            updates["rule_type"] = request.rule_type.strip()
        if request.jurisdiction is not None:
            updates["jurisdiction"] = request.jurisdiction.strip().upper()
        if request.regulator is not None:
            updates["regulator"] = request.regulator.strip()
        if request.description is not None:
            updates["description"] = request.description.strip()
        if request.extraction_confidence is not None:
            updates["extraction_confidence"] = request.extraction_confidence
        if request.effective_date is not None:
            updates["effective_date"] = request.effective_date
        if request.circular_number is not None:
            updates["circular_number"] = request.circular_number
        if request.validation_status is not None:
            updates["validation_status"] = request.validation_status
            if request.validation_status == "validated":
                updates.setdefault("validated_at", datetime.utcnow().isoformat())
        if request.is_active is not None:
            updates["is_active"] = request.is_active

        if rule_data_changed:
            updates["rule_data"] = rule_data

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        updates["updated_at"] = datetime.utcnow().isoformat()

        if is_manual_rule:
            manual_success = update_manual_rule(rule_id, updates)
            if not manual_success:
                raise HTTPException(status_code=500, detail="Failed to update manual compliance rule")
            logger.info("Manual compliance rule updated locally", rule_id=rule_id, updated_fields=list(updates.keys()))
            return {"status": "success", "rule_id": rule_id, "source": "manual-store"}

        success = await db.update_compliance_rule(rule_id, updates)
        if not success:
            # Fallback to manual store if Supabase update fails
            manual_success = update_manual_rule(rule_id, updates)
            if manual_success:
                logger.info(
                    "Compliance rule updated via manual store fallback",
                    rule_id=rule_id,
                    updated_fields=list(updates.keys())
                )
                return {"status": "success", "rule_id": rule_id, "source": "manual-store"}

            manual_payload = {
                **existing_record,
                **updates,
                "id": rule_id,
                "rule_data": rule_data if rule_data_changed else existing_record.get("rule_data", {}),
            }
            save_manual_rule(manual_payload)
            logger.info(
                "Compliance rule stored locally after Supabase update failure",
                rule_id=rule_id,
                updated_fields=list(updates.keys())
            )
            return {"status": "success", "rule_id": rule_id, "source": "manual-store"}

        logger.info("Compliance rule updated via API", rule_id=rule_id, updated_fields=list(updates.keys()))
        return {"status": "success", "rule_id": rule_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update compliance rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update compliance rule: {str(e)}")


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


class AuditEntryRequest(BaseModel):
    """Request to create an audit trail entry."""
    action: str
    user_name: str
    rules_created: int = 0
    rules_updated: int = 0
    status: Literal["success", "failed"] = "success"
    details: str = ""


@router.post("/audit-trail")
async def create_audit_entry(request: AuditEntryRequest):
    """
    Create a new audit trail entry.
    """
    db = get_supabase_service()

    try:
        import asyncio
        from datetime import datetime

        entry_data = {
            "action": request.action,
            "user_name": request.user_name,
            "rules_created": request.rules_created,
            "rules_updated": request.rules_updated,
            "status": request.status,
            "details": request.details,
            "timestamp": datetime.utcnow().isoformat(),
            "date_updated": datetime.utcnow().isoformat(),
        }

        result = await asyncio.to_thread(
            lambda: db.client.table("audit_trail")
            .insert(entry_data)
            .execute()
        )

        logger.info("Audit entry created", action=request.action, status=request.status)

        return {"status": "success", "entry": result.data[0]}

    except Exception as e:
        logger.error("Failed to create audit entry", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create audit entry: {str(e)}")


@router.get("/audit-trail")
async def get_audit_trail(limit: int = 100):
    """
    Get recent audit trail entries.
    """
    db = get_supabase_service()

    try:
        import asyncio

        result = await asyncio.to_thread(
            lambda: db.client.table("audit_trail")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )

        logger.info("Audit trail retrieved", count=len(result.data))

        return {"entries": result.data}

    except Exception as e:
        logger.error("Failed to retrieve audit trail", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve audit trail: {str(e)}")


@router.get("/rules/{rule_id}/confidence-analysis")
async def get_confidence_analysis(rule_id: str):
    """
    Get confidence analysis for a low-confidence rule.

    Returns explanation and clarification questions for rules with extraction_confidence < 0.95.
    """
    db = get_supabase_service()

    try:
        import asyncio

        # Fetch the rule
        response = await asyncio.to_thread(
            lambda: db.client.table("compliance_rules")
            .select("*")
            .eq("id", rule_id)
            .single()
            .execute()
        )

        if not response.data:
            raise HTTPException(status_code=404, detail="Rule not found")

        rule = response.data
        confidence = rule.get("extraction_confidence", 1.0)

        # Determine confidence tier
        if confidence > 0.95:
            return {
                "has_low_confidence": False,
                "tier": "high",
                "confidence": confidence,
                "reason": "Confidence level is high.",
                "questions": []
            }

        # Determine if moderate (80-95%) or low (< 80%)
        tier = "moderate" if confidence >= 0.80 else "low"

        analysis = await analyze_low_confidence(rule, tier)

        return {
            "has_low_confidence": True,
            "tier": tier,
            "confidence": confidence,
            "reason": analysis["reason"],
            "questions": analysis["questions"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to analyze confidence", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint for extraction service."""
    return {
        "status": "healthy",
        "service": "rule_extraction",
        "version": "1.0.0"
    }
