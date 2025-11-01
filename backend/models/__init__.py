"""
Data models for Payment History Analysis Tool.

This module contains Pydantic models for:
- Query parameters (input)
- Transaction records (CSV entities)
- Payment history (aggregated results)
- Analysis results (LLM output)
- Rules data (regulatory compliance)
"""

try:
    # Try backend-prefixed imports first (running from parent directory)
    from backend.models.query_params import QueryParameters
    from backend.models.transaction import TransactionRecord, PaymentHistory
    from backend.models.analysis_result import FlaggedTransaction, IdentifiedPattern, AnalysisResult
    from backend.models.rules import RulesData, ThresholdRule, ProhibitedJurisdiction, DocumentationRequirement
except ModuleNotFoundError:
    # Fall back to relative imports (running from backend directory)
    from models.query_params import QueryParameters
    from models.transaction import TransactionRecord, PaymentHistory
    from models.analysis_result import FlaggedTransaction, IdentifiedPattern, AnalysisResult
    from models.rules import RulesData, ThresholdRule, ProhibitedJurisdiction, DocumentationRequirement

__all__ = [
    "QueryParameters",
    "TransactionRecord",
    "PaymentHistory",
    "FlaggedTransaction",
    "IdentifiedPattern",
    "AnalysisResult",
    "RulesData",
    "ThresholdRule",
    "ProhibitedJurisdiction",
    "DocumentationRequirement",
]
