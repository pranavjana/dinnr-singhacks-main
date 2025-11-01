"""
Pydantic models for AML compliance rule data validation.
Feature: 003-langgraph-rule-extraction
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal
from datetime import datetime


# Rule Type Schemas (stored in compliance_rules.rule_data JSONB)

class ThresholdRule(BaseModel):
    """Transaction reporting threshold rule."""
    threshold_type: Literal["transaction_reporting", "ctr", "str", "cash_transaction"]
    amount: float = Field(gt=0, description="Threshold amount")
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")
    transaction_type: str
    applies_to: list[str] = Field(min_length=1, description="Applicable entity types")
    conditions: list[str] = Field(default_factory=list)
    exemptions: list[str] = Field(default_factory=list)
    source_text: str = Field(description="Exact quote from source document")
    page_reference: int | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        common_currencies = {"SGD", "USD", "EUR", "GBP", "HKD", "MYR", "CNY"}
        if v not in common_currencies:
            raise ValueError(f"Uncommon currency code: {v}")
        return v


class DeadlineRule(BaseModel):
    """Regulatory reporting deadline rule."""
    filing_type: str
    deadline_days: int = Field(gt=0, le=365)
    deadline_business_days: bool = Field(default=True)
    trigger_event: str
    penalties: str | None = None
    applies_to: list[str] = Field(min_length=1)
    source_text: str
    page_reference: int | None = None


class EDDTriggerRule(BaseModel):
    """Enhanced Due Diligence trigger rule."""
    trigger_category: Literal["pep", "high_risk_jurisdiction", "high_risk_customer", "complex_structure", "unusual_activity"]
    pep_tier: str | None = None
    relationship_types: list[str] = Field(min_length=1)
    required_approvals: list[str] = Field(default_factory=list)
    enhanced_measures: list[str] = Field(min_length=1, description="Required EDD measures")
    source_text: str
    page_reference: int | None = None


class SanctionsRule(BaseModel):
    """Sanctions screening and compliance rule."""
    sanctions_list: str
    screening_frequency: str
    match_threshold: float | None = Field(ge=0, le=1, default=None)
    escalation_procedures: list[str] = Field(default_factory=list)
    applies_to: list[str] = Field(min_length=1)
    source_text: str
    page_reference: int | None = None


class RecordKeepingRule(BaseModel):
    """Record retention and documentation rule."""
    record_type: str
    retention_period_years: int = Field(gt=0, le=100)
    storage_requirements: list[str] = Field(default_factory=list)
    applies_to: list[str] = Field(min_length=1)
    source_text: str
    page_reference: int | None = None


# Extraction Output Models

class ExtractedFact(BaseModel):
    """Single extracted fact from Analyser node."""
    rule_type: Literal["threshold", "deadline", "edd_trigger", "sanctions", "record_keeping"]
    confidence: float = Field(ge=0, le=1)
    rule_data: dict  # Will be validated against specific rule schema
    chunk_ids: list[str] = Field(description="Source embedding chunk UUIDs")
    model_reasoning: str | None = Field(default=None, description="Chain-of-thought explanation")


class NormalizedRule(BaseModel):
    """Normalized rule ready for database insertion."""
    rule_type: str
    jurisdiction: str
    regulator: str
    rule_schema_version: str = "v1"
    rule_data: dict
    circular_number: str | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    source_document_id: str
    extraction_confidence: float = Field(ge=0, le=1)
    extraction_model: str
    validation_status: Literal["pending", "validated", "rejected", "archived"] = "pending"


# Prompt Templates

RULE_TYPE_SCHEMAS = {
    "threshold": ThresholdRule,
    "deadline": DeadlineRule,
    "edd_trigger": EDDTriggerRule,
    "sanctions": SanctionsRule,
    "record_keeping": RecordKeepingRule,
}


def validate_rule_data(rule_type: str, rule_data: dict) -> dict:
    """
    Validate rule_data against appropriate Pydantic schema.

    Args:
        rule_type: Type of rule (threshold, deadline, etc.)
        rule_data: Raw extracted data

    Returns:
        Validated and normalized rule_data dict

    Raises:
        ValidationError: If data doesn't match schema
    """
    schema_class = RULE_TYPE_SCHEMAS.get(rule_type)
    if not schema_class:
        raise ValueError(f"Unknown rule_type: {rule_type}")

    validated = schema_class(**rule_data)
    return validated.model_dump()


# Cost calculation constants (Groq pricing)
KIMI_K2_INPUT_COST_PER_1M = 0.30  # USD
KIMI_K2_OUTPUT_COST_PER_1M = 1.20  # USD


def calculate_extraction_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for Groq Kimi K2 API call."""
    input_cost = (input_tokens / 1_000_000) * KIMI_K2_INPUT_COST_PER_1M
    output_cost = (output_tokens / 1_000_000) * KIMI_K2_OUTPUT_COST_PER_1M
    return round(input_cost + output_cost, 6)
