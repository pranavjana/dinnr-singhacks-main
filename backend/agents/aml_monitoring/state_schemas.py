"""
State schemas for LangGraph payment analysis workflow.
Defines the shared state passed between agent nodes.
"""
from typing import TypedDict, Literal, List, Dict, Any, Optional
from uuid import UUID


class PaymentAnalysisState(TypedDict):
    """
    Shared state for payment analysis LangGraph workflow.
    
    This state is passed between all nodes in the graph and accumulates
    information as the analysis progresses.
    """
    # Input
    payment: Dict[str, Any]  # Payment transaction data
    payment_id: UUID
    trace_id: UUID
    
    # Historical data (from feature 001)
    historical_transactions: List[Dict[str, Any]]
    
    # Analysis results
    triggered_rules: List[Dict[str, Any]]  # Rules that were violated
    detected_patterns: List[Dict[str, Any]]  # Patterns found in history
    llm_flagged_transactions: List[Dict[str, Any]]  # Transactions flagged by LLM
    llm_patterns: List[Dict[str, Any]]  # Patterns identified by LLM
    
    # Scoring
    rule_score: float
    pattern_score: float
    risk_score: float
    llm_risk_score: float
    
    # Final verdict
    verdict: Literal["pass", "suspicious", "fail"]
    assigned_team: Literal["front_office", "compliance", "legal"]
    justification: str
    llm_summary: str
    
    # Metadata
    analysis_start_time: float
    analysis_duration_ms: int
    llm_model: str
    
    # Error handling
    errors: List[str]
