"""
LangGraph workflow for AML compliance rule extraction.
Feature: 003-langgraph-rule-extraction
"""

import uuid
import structlog
from datetime import datetime
from typing import Literal
from langgraph.graph import StateGraph, END
from workflows.schemas.extraction_state import ExtractionState, create_initial_state
from workflows.nodes.analyser import analyser_node
from workflows.nodes.rules_tool import rules_tool_node
from services.supabase_service import get_supabase_service

logger = structlog.get_logger(__name__)


def should_retry_analyser(state: ExtractionState) -> Literal["analyser", "rules_tool", "__end__"]:
    """
    Conditional edge: Determine if Analyser should retry or proceed.

    Logic:
    - If status == "failed" and retry_count < max_retries → retry analyser
    - If extracted_facts exist → proceed to rules_tool
    - Otherwise → end workflow
    """
    status = state.get("status", "running")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    extracted_facts = state.get("extracted_facts", [])

    logger.info(
        "Evaluating analyser retry condition",
        status=status,
        retry_count=retry_count,
        facts_extracted=len(extracted_facts)
    )

    # Retry on failure if retries remaining
    if status == "failed" and retry_count < max_retries:
        logger.warning(f"Analyser failed, retrying ({retry_count}/{max_retries})")
        return "analyser"

    # Proceed to rules_tool if facts extracted
    if extracted_facts:
        logger.info("Proceeding to rules_tool node")
        return "rules_tool"

    # End workflow if no facts and max retries exceeded
    logger.error("No facts extracted and max retries exceeded, ending workflow")
    return END


def should_continue_after_rules_tool(state: ExtractionState) -> Literal["__end__"]:
    """
    Conditional edge: Always end after rules_tool completes.

    In future, could add human-in-loop validation step here.
    """
    status = state.get("status", "completed")
    logger.info(f"Rules Tool completed with status: {status}")
    return END


# Build the LangGraph workflow
def create_extraction_workflow() -> StateGraph:
    """
    Create the LangGraph state graph for rule extraction.

    Workflow:
    1. Start → Analyser Node
    2. Analyser → (retry if failed) → Rules Tool Node
    3. Rules Tool → End

    Returns:
        Compiled StateGraph
    """
    workflow = StateGraph(ExtractionState)

    # Add nodes
    workflow.add_node("analyser", analyser_node)
    workflow.add_node("rules_tool", rules_tool_node)

    # Set entry point
    workflow.set_entry_point("analyser")

    # Conditional edges
    workflow.add_conditional_edges(
        "analyser",
        should_retry_analyser,
        {
            "analyser": "analyser",  # Retry path
            "rules_tool": "rules_tool",  # Success path
            END: END,  # Failure path
        }
    )

    workflow.add_conditional_edges(
        "rules_tool",
        should_continue_after_rules_tool,
        {
            END: END,
        }
    )

    return workflow.compile()


# Singleton workflow instance
_workflow_instance = None


def get_extraction_workflow() -> StateGraph:
    """Get or create compiled extraction workflow."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = create_extraction_workflow()
    return _workflow_instance


# High-level execution functions

async def extract_rules_from_document(
    document_id: str,
    jurisdiction: str,
    target_rule_types: list[str] | None = None,
    max_retries: int = 3,
) -> dict:
    """
    Execute rule extraction workflow for a single document.

    Args:
        document_id: UUID of document to process
        jurisdiction: Jurisdiction code (e.g., 'SG')
        target_rule_types: List of rule types to extract (default: all)
        max_retries: Max retry attempts for Analyser node

    Returns:
        Final workflow state as dict
    """
    workflow_run_id = str(uuid.uuid4())

    if target_rule_types is None:
        target_rule_types = ["threshold", "deadline", "edd_trigger", "sanctions", "record_keeping"]

    logger.info(
        "Starting rule extraction workflow",
        workflow_run_id=workflow_run_id,
        document_id=document_id,
        jurisdiction=jurisdiction,
        target_rule_types=target_rule_types
    )

    # Create initial state
    initial_state = create_initial_state(
        workflow_run_id=workflow_run_id,
        document_id=document_id,
        target_rule_types=target_rule_types,
        jurisdiction=jurisdiction,
        max_retries=max_retries,
    )

    # Get compiled workflow
    workflow = get_extraction_workflow()

    try:
        # Execute workflow
        final_state = await workflow.ainvoke(initial_state)

        # Log workflow metrics
        await _log_workflow_metrics(final_state)

        logger.info(
            "Workflow completed",
            workflow_run_id=workflow_run_id,
            status=final_state.get("status"),
            rules_created=len(final_state.get("rule_ids_created", [])),
            total_cost=final_state.get("cost_usd", 0.0)
        )

        return final_state

    except Exception as e:
        logger.error(
            "Workflow execution failed",
            workflow_run_id=workflow_run_id,
            error=str(e),
            exc_info=True
        )
        raise


async def extract_rules_batch(
    document_ids: list[str],
    jurisdiction: str,
    target_rule_types: list[str] | None = None,
) -> list[dict]:
    """
    Execute rule extraction for multiple documents in batch.

    Args:
        document_ids: List of document UUIDs
        jurisdiction: Jurisdiction code
        target_rule_types: Rule types to extract

    Returns:
        List of final states for each document
    """
    import asyncio

    logger.info(f"Starting batch extraction for {len(document_ids)} documents")

    # Execute all documents concurrently
    tasks = [
        extract_rules_from_document(doc_id, jurisdiction, target_rule_types)
        for doc_id in document_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions
    successful_results = [r for r in results if not isinstance(r, Exception)]
    failed_count = len(results) - len(successful_results)

    logger.info(
        "Batch extraction completed",
        total=len(document_ids),
        successful=len(successful_results),
        failed=failed_count
    )

    return successful_results


async def _log_workflow_metrics(state: ExtractionState) -> None:
    """
    Log workflow metrics to extraction_metrics table.

    Args:
        state: Final workflow state
    """
    db = get_supabase_service()

    start_time = state.get("start_time")
    end_time = state.get("end_time", datetime.utcnow())

    if isinstance(start_time, datetime) and isinstance(end_time, datetime):
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
    else:
        duration_ms = 0

    metrics = {
        "workflow_run_id": state["workflow_run_id"],
        "trigger_type": "api",  # Could be "scheduled", "webhook", etc.
        "documents_processed": 1,
        "rules_created": len(state.get("rule_ids_created", [])),
        "rules_updated": len(state.get("rule_ids_updated", [])),
        "avg_confidence": state.get("analyser_confidence", 0.0),
        "validation_pass_rate": None,  # Will be updated after human validation
        "human_review_required": _count_low_confidence_rules(state),
        "total_duration_ms": duration_ms,
        "total_cost_usd": state.get("cost_usd", 0.0),
        "total_tokens_used": state.get("tokens_used", 0),
        "failed_documents": 1 if state.get("status") == "failed" else 0,
        "error_summary": {
            "analyser_errors": state.get("analyser_errors", []),
            "status": state.get("status"),
        } if state.get("status") == "failed" else None,
    }

    await db.log_workflow_metrics(metrics)


def _count_low_confidence_rules(state: ExtractionState) -> int:
    """Count rules with confidence < 0.8 requiring human review."""
    facts = state.get("extracted_facts", [])
    return sum(1 for fact in facts if fact.get("confidence", 0) < 0.8)
