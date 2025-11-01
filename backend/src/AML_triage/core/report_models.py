"""Pydantic models describing the LLM3 to LLM4 payload contract."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationError, field_validator


class SimpleSignal(BaseModel):
    rule_id: str
    title: Optional[str] = None
    explanation: Optional[str] = None


class PrimaryActionChecks(BaseModel):
    met: Optional[bool] = None
    details: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)


class PrimaryAction(BaseModel):
    action_id: str
    template_id: Optional[str] = None
    confidence: Optional[float] = None
    approvals_required: Optional[bool] = None
    preconditions_check: PrimaryActionChecks | None = None
    action_params: Dict[str, Any] = Field(default_factory=dict)


class AlternativeAction(BaseModel):
    action_id: str
    confidence: Optional[float] = None
    approvals_required: Optional[bool] = None
    why_not_primary: Optional[str] = None
    template_id: Optional[str] = None
    for_signals: List[str] = Field(default_factory=list)


class RankedAction(BaseModel):
    action_id: str
    confidence: Optional[float] = None
    for_signals: List[str] = Field(default_factory=list)
    template_tags: List[str] = Field(default_factory=list)


class BehaviourSummary(BaseModel):
    credits_count: Optional[int] = None
    debits_count: Optional[int] = None
    median_turnaround_hours: Optional[float] = None
    unique_beneficiaries: Optional[int] = None


class TransactionSnapshot(BaseModel):
    transaction_ref: Optional[str] = None
    booking_datetime: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    channel: Optional[str] = None
    product_type: Optional[str] = None
    originator_name: Optional[str] = None
    originator_account_masked: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_account_masked: Optional[str] = None
    countries: List[str] = Field(default_factory=list)
    sanctions_screening: Optional[str] = None
    edd_required: Optional[bool] = None
    edd_performed: Optional[bool] = None
    str_filed_datetime: Optional[str] = None
    behaviour_summary_30d: Optional[BehaviourSummary] = None


class LLM3Payload(BaseModel):
    schema: str
    schema_version: str = Field(pattern=r"^v[0-9]+$")
    trace_id: str
    decision: str
    risk_level: Optional[str] = None
    signals: List[Union[str, SimpleSignal]] = Field(default_factory=list)
    profile_considerations: Dict[str, Any] = Field(default_factory=dict)
    primary_action: Optional[PrimaryAction] = None
    alternatives: List[AlternativeAction] = Field(default_factory=list)
    ranked_actions: List[RankedAction] = Field(default_factory=list)
    txn_snapshot: Optional[TransactionSnapshot] = None
    templates_used: List[str] = Field(default_factory=list)
    catalogue_constraints: Dict[str, Any] = Field(default_factory=dict)
    notes_for_llm4: List[str] = Field(default_factory=list)
    needs_human_review: Optional[bool] = None

    @field_validator("decision")
    @classmethod
    def _normalise_decision(cls, value: str) -> str:
        return value.upper()

    def resolved_signals(self) -> List[SimpleSignal]:
        resolved: List[SimpleSignal] = []
        for item in self.signals:
            if isinstance(item, str):
                resolved.append(SimpleSignal(rule_id=item))
            else:
                resolved.append(item)
        return resolved

    def recommended_actions(self) -> List[str]:
        if self.primary_action:
            ids = [self.primary_action.action_id]
            ids.extend(action.action_id for action in self.alternatives)
            return ids
        if self.ranked_actions:
            # Already ordered by LLM3
            return [action.action_id for action in self.ranked_actions]
        return []

    def top_ranked_action(self) -> Optional[str]:
        actions = self.recommended_actions()
        return actions[0] if actions else None


__all__ = ["LLM3Payload", "PrimaryAction", "AlternativeAction", "RankedAction", "SimpleSignal", "TransactionSnapshot"]
