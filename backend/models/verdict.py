"""
Verdict model for payment risk assessment outcomes.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4
from enum import Enum


class VerdictType(str, Enum):
    """Risk verdict types."""
    PASS = "pass"
    SUSPICIOUS = "suspicious"
    FAIL = "fail"


class TeamAssignment(str, Enum):
    """Team assignments for alert routing."""
    FRONT_OFFICE = "front_office"
    COMPLIANCE = "compliance"
    LEGAL = "legal"


class Verdict(BaseModel):
    """Risk assessment verdict for a payment."""
    
    verdict_id: UUID = Field(default_factory=uuid4)
    payment_id: UUID = Field(..., description="Foreign key to payments table")
    trace_id: UUID = Field(..., description="LangGraph execution trace ID")
    
    # Verdict
    verdict: VerdictType
    assigned_team: TeamAssignment
    risk_score: float = Field(..., ge=0, le=100, description="Combined risk score (0-100)")
    
    # Analysis components
    rule_score: float = Field(..., ge=0, description="Score from triggered rules")
    pattern_score: float = Field(..., ge=0, description="Score from detected patterns")
    
    # Justification
    justification: str = Field(..., min_length=10, description="Human-readable explanation")
    
    # Timing
    analysis_duration_ms: int = Field(..., gt=0)
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Model metadata
    llm_model: str = Field(default="kimi-k2-0905")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "payment_id": "123e4567-e89b-12d3-a456-426614174000",
                "trace_id": "789e4567-e89b-12d3-a456-426614174111",
                "verdict": "suspicious",
                "assigned_team": "compliance",
                "risk_score": 45,
                "rule_score": 20,
                "pattern_score": 25,
                "justification": "Detected velocity anomaly: 8 transactions in 7 days (5σ above baseline). No explicit rule violations.",
                "analysis_duration_ms": 450
            }
        }
    }


class AnalysisResult(BaseModel):
    """Complete analysis result returned to API client."""
    
    payment_id: UUID
    trace_id: UUID
    verdict: VerdictType
    assigned_team: TeamAssignment
    risk_score: float
    justification: str
    analysis_duration_ms: int
    triggered_rules: list = Field(default_factory=list)
    detected_patterns: list = Field(default_factory=list)
    alert_id: UUID | None = None  # Present if verdict is suspicious or fail
