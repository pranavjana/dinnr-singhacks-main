"""
LangGraph State Schema for AML Compliance Rule Extraction
Feature: 003-langgraph-rule-extraction
"""

from typing import TypedDict, Annotated, Literal
from datetime import datetime
import operator


class ExtractionState(TypedDict):
    """
    Workflow state shared between Analyser and Rules Tool nodes.

    Uses Annotated types with operator.add for append-only collections
    to ensure proper state accumulation across node executions.
    """

    # Input configuration
    workflow_run_id: str
    document_id: str
    target_rule_types: list[str]  # ['threshold', 'deadline', 'edd_trigger']
    jurisdiction: str  # 'SG', 'HK', 'MY', etc.

    # Document context
    document_metadata: dict  # From document_metadata table
    full_text: str  # Complete extracted_text from documents table
    circular_number: str
    issuing_authority: str
    effective_date: str | None

    # Analyser outputs (append-only)
    retrieved_chunks: list[dict]  # Embedding chunks with metadata
    extracted_facts: Annotated[list[dict], operator.add]  # Accumulate facts
    analyser_confidence: float
    analyser_errors: Annotated[list[str], operator.add]  # Accumulate errors

    # Rules Tool outputs (append-only)
    normalized_rules: list[dict]  # Final compliance_rules records
    rule_ids_created: Annotated[list[str], operator.add]
    rule_ids_updated: Annotated[list[str], operator.add]
    deduplication_summary: dict

    # Workflow control
    current_node: str
    retry_count: int
    max_retries: int
    status: Literal["running", "completed", "failed", "partial"]

    # Metrics (accumulate across retries)
    tokens_used: Annotated[int, operator.add]
    cost_usd: Annotated[float, operator.add]
    api_calls: Annotated[int, operator.add]
    start_time: datetime
    end_time: datetime | None


def create_initial_state(
    workflow_run_id: str,
    document_id: str,
    target_rule_types: list[str],
    jurisdiction: str,
    max_retries: int = 3
) -> ExtractionState:
    """
    Factory function to create initial workflow state with proper defaults.

    Args:
        workflow_run_id: Unique ID for this workflow execution
        document_id: UUID of document to process
        target_rule_types: List of rule types to extract
        jurisdiction: Regulatory jurisdiction code
        max_retries: Maximum retry attempts for failed nodes

    Returns:
        Initialized ExtractionState
    """
    return {
        # Input configuration
        "workflow_run_id": workflow_run_id,
        "document_id": document_id,
        "target_rule_types": target_rule_types,
        "jurisdiction": jurisdiction,

        # Document context (populated by Analyser)
        "document_metadata": {},
        "full_text": "",
        "circular_number": "",
        "issuing_authority": "",
        "effective_date": None,

        # Analyser outputs
        "retrieved_chunks": [],
        "extracted_facts": [],
        "analyser_confidence": 0.0,
        "analyser_errors": [],

        # Rules Tool outputs
        "normalized_rules": [],
        "rule_ids_created": [],
        "rule_ids_updated": [],
        "deduplication_summary": {},

        # Workflow control
        "current_node": "analyser",
        "retry_count": 0,
        "max_retries": max_retries,
        "status": "running",

        # Metrics
        "tokens_used": 0,
        "cost_usd": 0.0,
        "api_calls": 0,
        "start_time": datetime.utcnow(),
        "end_time": None,
    }
