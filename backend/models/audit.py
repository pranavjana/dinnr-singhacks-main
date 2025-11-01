"""
Audit log model for immutable tracking of all payment analyses.
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


class AuditLog(BaseModel):
    """Immutable audit log for payment analysis."""
    
    audit_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(..., description="LangGraph execution trace")
    payment_id: UUID
    verdict_id: Optional[UUID] = None
    
    # Decision
    action: str = Field(..., description="Action taken (e.g., 'verdict_assigned', 'alert_created')")
    actor: str = Field(..., description="Agent name or user ID")
    
    # Details
    decision_type: str
    decision_rationale: str
    regulatory_references: list[str] = Field(default_factory=list)
    
    # Audit metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    llm_model: Optional[str] = None
    reasoning_chain: Optional[dict] = Field(None, description="LangGraph state snapshot")
    
    model_config = ConfigDict(
        # Immutable - prevent modifications after creation
        frozen=True,
        json_schema_extra={
            "example": {
                "trace_id": "789e4567-e89b-12d3-a456-426614174111",
                "payment_id": "123e4567-e89b-12d3-a456-426614174000",
                "action": "verdict_assigned",
                "actor": "PaymentAnalysisAgent",
                "decision_type": "risk_assessment",
                "decision_rationale": "Payment analyzed against AML rules and patterns, assigned suspicious verdict",
                "regulatory_references": ["FINMA-Circular-2016/7"],
                "llm_model": "kimi-k2-0905"
            }
        }
    )
