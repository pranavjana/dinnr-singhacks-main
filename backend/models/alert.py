"""
Alert model for flagged payments requiring review.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID, uuid4
from enum import Enum


class AlertPriority(str, Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status values."""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class Alert(BaseModel):
    """Alert for flagged payment requiring review."""
    
    alert_id: UUID = Field(default_factory=uuid4)
    verdict_id: UUID = Field(..., description="Foreign key to verdicts table")
    payment_id: UUID = Field(..., description="Foreign key to payments table")
    
    # Alert details
    assigned_team: str  # front_office, compliance, or legal
    priority: AlertPriority
    status: AlertStatus = Field(default=AlertStatus.PENDING)
    
    # Triggered rules and patterns
    triggered_rule_ids: list[UUID] = Field(default_factory=list)
    detected_pattern_types: list[str] = Field(default_factory=list)
    
    # Recommendations
    investigation_steps: list[str] = Field(..., min_length=1)
    
    # Lifecycle
    created_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = Field(None, description="User ID of assigned reviewer")
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "verdict_id": "456e4567-e89b-12d3-a456-426614174222",
                "payment_id": "123e4567-e89b-12d3-a456-426614174000",
                "assigned_team": "compliance",
                "priority": "medium",
                "status": "pending",
                "triggered_rule_ids": [],
                "detected_pattern_types": ["velocity"],
                "investigation_steps": [
                    "Review transaction frequency over past 30 days",
                    "Verify source of funds documentation",
                    "Check for related party transactions"
                ]
            }
        }
    }


class AlertUpdate(BaseModel):
    """Model for updating alert status."""
    status: Optional[AlertStatus] = None
    assigned_to: Optional[str] = None
    resolution_notes: Optional[str] = None
