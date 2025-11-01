# Data Model: Rules-Based Payment Analysis Integration

**Feature**: 004-rules-payment-integration
**Date**: 2025-11-01
**Status**: Design Complete

## Overview

This document defines the data structures, database schema, and entity relationships for the integrated payment analysis system combining rule checking and pattern detection for AML risk assessment.

## Entity Relationship Diagram

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│    Payment      │────────>│     Verdict      │────────>│      Alert      │
│  Transaction    │  1:1    │                  │  0:1    │                  │
└─────────────────┘         └──────────────────┘         └─────────────────┘
         │                           │                            │
         │                           │                            │
         │ N:1                       │ N:M                        │ 1:1
         │                           │                            │
         ▼                           ▼                            ▼
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│Payment History  │         │ Triggered Rules  │         │   Audit Log     │
│  (Feature 001)  │         │  (Feature 003)   │         │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
         │                           │
         │                           │
         │ 1:N                       │ N:M
         │                           │
         ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│    Pattern      │         │ Compliance Rule  │
│   Detection     │         │  (Feature 003)   │
└─────────────────┘         └──────────────────┘
```

## Core Entities

### 1. PaymentTransaction

Represents a single payment submission for AML risk analysis.

**Source**: User submission via API (or batch processing)

**Pydantic Model**:
```python
from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from typing import Optional

class PaymentTransaction(BaseModel):
    """Payment transaction submitted for AML analysis"""
    payment_id: UUID4 = Field(default_factory=uuid4, description="Unique payment identifier")

    # Payer information
    originator_name: str = Field(..., min_length=1, max_length=200)
    originator_account: str = Field(..., min_length=1, max_length=50)
    originator_country: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2")

    # Beneficiary information
    beneficiary_name: str = Field(..., min_length=1, max_length=200)
    beneficiary_account: str = Field(..., min_length=1, max_length=50)
    beneficiary_country: str = Field(..., min_length=2, max_length=2)

    # Transaction details
    amount: float = Field(..., gt=0, description="Transaction amount in base currency")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO 4217 currency code")
    transaction_date: datetime
    value_date: datetime

    # SWIFT fields
    swift_message_type: str = Field(..., regex=r"MT\d{3}")
    ordering_institution: Optional[str] = Field(None, max_length=200)
    beneficiary_institution: Optional[str] = Field(None, max_length=200)

    # Screening flags (from upstream systems)
    sanctions_screening_result: Optional[str] = Field(None, description="PASS/FAIL/REVIEW")
    pep_screening_result: Optional[str] = Field(None)

    # Metadata
    submission_timestamp: datetime = Field(default_factory=datetime.utcnow)
    submitted_by: Optional[str] = Field(None, description="User ID of submitter")

    class Config:
        json_schema_extra = {
            "example": {
                "originator_name": "Jennifer Parker",
                "originator_account": "GB39OOLA52427580832378",
                "originator_country": "GB",
                "beneficiary_name": "George Brown",
                "beneficiary_account": "GB88KUDJ48147748190437",
                "beneficiary_country": "SG",
                "amount": 15000.00,
                "currency": "USD",
                "transaction_date": "2025-11-01T10:30:00Z",
                "value_date": "2025-11-01T10:30:00Z",
                "swift_message_type": "MT103",
                "sanctions_screening_result": "PASS"
            }
        }
```

**Database Table**:
```sql
CREATE TABLE payments (
    payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Payer
    originator_name VARCHAR(200) NOT NULL,
    originator_account VARCHAR(50) NOT NULL,
    originator_country CHAR(2) NOT NULL,

    -- Beneficiary
    beneficiary_name VARCHAR(200) NOT NULL,
    beneficiary_account VARCHAR(50) NOT NULL,
    beneficiary_country CHAR(2) NOT NULL,

    -- Transaction
    amount DECIMAL(20, 2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL,
    value_date TIMESTAMPTZ NOT NULL,

    -- SWIFT
    swift_message_type VARCHAR(10) NOT NULL,
    ordering_institution VARCHAR(200),
    beneficiary_institution VARCHAR(200),

    -- Screening
    sanctions_screening_result VARCHAR(20),
    pep_screening_result VARCHAR(20),

    -- Metadata
    submission_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_by VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_originator ON payments(originator_account, originator_name);
CREATE INDEX idx_payments_beneficiary ON payments(beneficiary_account, beneficiary_name);
CREATE INDEX idx_payments_date ON payments(transaction_date DESC);
```

### 2. Verdict

The risk assessment outcome for a payment after analysis.

**Pydantic Model**:
```python
from typing import Literal
from enum import Enum

class VerdictType(str, Enum):
    PASS = "pass"
    SUSPICIOUS = "suspicious"
    FAIL = "fail"

class TeamAssignment(str, Enum):
    FRONT_OFFICE = "front_office"
    COMPLIANCE = "compliance"
    LEGAL = "legal"

class Verdict(BaseModel):
    """Risk assessment verdict for a payment"""
    verdict_id: UUID4 = Field(default_factory=uuid4)
    payment_id: UUID4 = Field(..., description="Foreign key to payments table")
    trace_id: UUID4 = Field(..., description="LangGraph execution trace ID")

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

    class Config:
        json_schema_extra = {
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
```

**Database Table**:
```sql
CREATE TABLE verdicts (
    verdict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,
    trace_id UUID NOT NULL UNIQUE,

    verdict VARCHAR(20) NOT NULL CHECK (verdict IN ('pass', 'suspicious', 'fail')),
    assigned_team VARCHAR(20) NOT NULL CHECK (assigned_team IN ('front_office', 'compliance', 'legal')),
    risk_score DECIMAL(5, 2) NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),

    rule_score DECIMAL(5, 2) NOT NULL,
    pattern_score DECIMAL(5, 2) NOT NULL,

    justification TEXT NOT NULL,

    analysis_duration_ms INTEGER NOT NULL,
    analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    llm_model VARCHAR(100) NOT NULL DEFAULT 'kimi-k2-0905',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verdicts_payment ON verdicts(payment_id);
CREATE INDEX idx_verdicts_trace ON verdicts(trace_id);
CREATE INDEX idx_verdicts_verdict ON verdicts(verdict, assigned_team);
CREATE INDEX idx_verdicts_timestamp ON verdicts(analysis_timestamp DESC);
```

### 3. Alert

Generated for payments with "suspicious" or "fail" verdicts requiring human review.

**Pydantic Model**:
```python
from typing import List

class AlertPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Alert(BaseModel):
    """Alert for flagged payment requiring review"""
    alert_id: UUID4 = Field(default_factory=uuid4)
    verdict_id: UUID4 = Field(..., description="Foreign key to verdicts table")
    payment_id: UUID4 = Field(..., description="Foreign key to payments table")

    # Alert details
    assigned_team: TeamAssignment
    priority: AlertPriority
    status: Literal["pending", "under_review", "resolved", "escalated"] = "pending"

    # Triggered rules and patterns
    triggered_rule_ids: List[UUID4] = Field(default_factory=list)
    detected_pattern_types: List[str] = Field(default_factory=list)

    # Recommendations
    investigation_steps: List[str] = Field(..., min_items=1)

    # Lifecycle
    created_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = Field(None, description="User ID of assigned reviewer")
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    class Config:
        json_schema_extra = {
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
```

**Database Table**:
```sql
CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict_id UUID NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,

    assigned_team VARCHAR(20) NOT NULL CHECK (assigned_team IN ('front_office', 'compliance', 'legal')),
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'under_review', 'resolved', 'escalated')),

    triggered_rule_ids UUID[] DEFAULT '{}',
    detected_pattern_types TEXT[] DEFAULT '{}',

    investigation_steps JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_to VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_verdict ON alerts(verdict_id);
CREATE INDEX idx_alerts_payment ON alerts(payment_id);
CREATE INDEX idx_alerts_team_status ON alerts(assigned_team, status);
CREATE INDEX idx_alerts_priority ON alerts(priority, created_at DESC);
```

### 4. TriggeredRule

Junction table linking verdicts to compliance rules that were violated.

**Pydantic Model**:
```python
class TriggeredRule(BaseModel):
    """Compliance rule triggered during payment analysis"""
    triggered_rule_id: UUID4 = Field(default_factory=uuid4)
    verdict_id: UUID4
    rule_id: UUID4 = Field(..., description="Foreign key to compliance_rules (feature 003)")

    # Rule details (denormalized for performance)
    rule_type: str
    jurisdiction: str
    regulator: str
    severity: Literal["low", "medium", "high", "critical"]

    # Evidence
    evidence: dict = Field(..., description="Why this rule was triggered")

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Database Table**:
```sql
CREATE TABLE triggered_rules (
    triggered_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict_id UUID NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES compliance_rules(id) ON DELETE RESTRICT,

    -- Denormalized for query performance
    rule_type VARCHAR(100) NOT NULL,
    jurisdiction VARCHAR(10) NOT NULL,
    regulator VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),

    evidence JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(verdict_id, rule_id)
);

CREATE INDEX idx_triggered_rules_verdict ON triggered_rules(verdict_id);
CREATE INDEX idx_triggered_rules_rule ON triggered_rules(rule_id);
CREATE INDEX idx_triggered_rules_type ON triggered_rules(rule_type);
```

### 5. DetectedPattern

Patterns identified in payment history during analysis.

**Pydantic Model**:
```python
class PatternType(str, Enum):
    STRUCTURING = "structuring"
    VELOCITY = "velocity"
    JURISDICTIONAL = "jurisdictional"
    ROUND_TRIPPING = "round_tripping"
    LAYERING = "layering"

class DetectedPattern(BaseModel):
    """Money laundering pattern detected during analysis"""
    pattern_id: UUID4 = Field(default_factory=uuid4)
    verdict_id: UUID4
    payment_id: UUID4

    pattern_type: PatternType
    confidence: float = Field(..., ge=0, le=1, description="Confidence score 0-1")

    # Evidence
    evidence: dict = Field(..., description="Supporting transactions and metrics")
    description: str = Field(..., min_length=10)

    # Risk contribution
    risk_multiplier: float = Field(default=1.0, ge=0, le=10)

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Database Table**:
```sql
CREATE TABLE detected_patterns (
    pattern_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict_id UUID NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,

    pattern_type VARCHAR(50) NOT NULL CHECK (pattern_type IN ('structuring', 'velocity', 'jurisdictional', 'round_tripping', 'layering')),
    confidence DECIMAL(3, 2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),

    evidence JSONB NOT NULL,
    description TEXT NOT NULL,

    risk_multiplier DECIMAL(4, 2) NOT NULL DEFAULT 1.0 CHECK (risk_multiplier >= 0 AND risk_multiplier <= 10),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_detected_patterns_verdict ON detected_patterns(verdict_id);
CREATE INDEX idx_detected_patterns_payment ON detected_patterns(payment_id);
CREATE INDEX idx_detected_patterns_type ON detected_patterns(pattern_type);
```

### 6. AuditLog

Immutable audit trail for all payment analyses (constitutional requirement).

**Pydantic Model**:
```python
class AuditLog(BaseModel):
    """Immutable audit log for payment analysis"""
    audit_id: UUID4 = Field(default_factory=uuid4)
    trace_id: UUID4 = Field(..., description="LangGraph execution trace")
    payment_id: UUID4
    verdict_id: Optional[UUID4] = None

    # Decision
    action: str = Field(..., description="Action taken (e.g., 'verdict_assigned', 'alert_created')")
    actor: str = Field(..., description="Agent name or user ID")

    # Details
    decision_type: str
    decision_rationale: str
    regulatory_references: List[str] = Field(default_factory=list)

    # Audit metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    llm_model: Optional[str] = None
    reasoning_chain: Optional[dict] = Field(None, description="LangGraph state snapshot")

    class Config:
        # Immutable
        allow_mutation = False
```

**Database Table**:
```sql
CREATE TABLE audit_logs (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID NOT NULL,
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE RESTRICT,
    verdict_id UUID REFERENCES verdicts(verdict_id) ON DELETE RESTRICT,

    action VARCHAR(100) NOT NULL,
    actor VARCHAR(200) NOT NULL,

    decision_type VARCHAR(100) NOT NULL,
    decision_rationale TEXT NOT NULL,
    regulatory_references TEXT[] DEFAULT '{}',

    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    llm_model VARCHAR(100),
    reasoning_chain JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Prevent updates and deletes (append-only)
CREATE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

CREATE INDEX idx_audit_logs_trace ON audit_logs(trace_id);
CREATE INDEX idx_audit_logs_payment ON audit_logs(payment_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
```

## State Transitions

### Verdict Lifecycle
```
Payment Submitted → Analysis Started → Rules Checked → Patterns Detected → Verdict Assigned → [Alert Created if not "pass"] → Audit Logged
```

### Alert Lifecycle
```
Alert Created (pending) → Assigned to User (under_review) → Investigation → [Resolved | Escalated]
```

## Validation Rules

1. **Payment Transaction**:
   - Amount must be > 0
   - Currency must be valid ISO 4217 code
   - Countries must be valid ISO 3166-1 alpha-2 codes
   - SWIFT message type must match MT### pattern

2. **Verdict**:
   - Risk score must be 0-100
   - Rule score + pattern score should approximately equal risk score
   - Verdict must match risk score ranges (pass<30, suspicious 30-69, fail≥70)
   - Justification required (min 10 characters)

3. **Alert**:
   - Only created for "suspicious" or "fail" verdicts
   - Must have at least one investigation step
   - Status transitions: pending→under_review→resolved/escalated (one-way)

4. **Triggered Rules**:
   - Rule must exist in compliance_rules table (foreign key constraint)
   - Unique constraint on (verdict_id, rule_id) prevents duplicates

5. **Detected Patterns**:
   - Confidence must be 0-1
   - Evidence field must contain supporting data

6. **Audit Logs**:
   - Immutable (no updates/deletes allowed)
   - Every verdict must have corresponding audit log entry

## Performance Considerations

- **Indexes**: All foreign keys indexed, plus composite indexes on query patterns (team+status, verdict+timestamp)
- **Partitioning**: Consider partitioning `audit_logs` by month for long-term scalability
- **Denormalization**: `triggered_rules` stores rule_type/jurisdiction for faster querying without joins
- **Connection Pooling**: Supabase pooler configured for 20 connections (100 concurrent requests)

## Data Retention

- **Payments**: Retain indefinitely (regulatory requirement)
- **Verdicts**: Retain indefinitely (audit requirement)
- **Alerts**: Retain indefinitely (compliance requirement)
- **Audit Logs**: Retain for 7 years (standard AML retention period)
- **Triggered Rules**: Retain indefinitely (linked to verdicts)
- **Detected Patterns**: Retain indefinitely (linked to verdicts)
