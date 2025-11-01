"""
Payment Analysis Router - endpoints for single-payment analysis, streaming updates,
and AML triage integration.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from backend.models.transaction import TransactionRecord as PaymentTransaction
    from backend.agents.aml_monitoring.payment_analysis_agent import (
        analyze_payment,
        collect_related_transactions,
        generate_streaming_analysis,
    )
    from backend.services.transaction_service import transaction_service
    from backend.services.rules_service import rules_service
    from backend.src.AML_triage.core.config import load_settings
    from backend.src.AML_triage.core.report_generator import ReportGenerator, ReportGenerationError
    from backend.src.AML_triage.core.validation import SchemaValidationError, hash_payload
except ModuleNotFoundError:
    from models.transaction import TransactionRecord as PaymentTransaction
    from agents.aml_monitoring.payment_analysis_agent import (
        analyze_payment,
        collect_related_transactions,
        generate_streaming_analysis,
    )
    from services.transaction_service import transaction_service
    from services.rules_service import rules_service
    from src.AML_triage.core.config import load_settings
    from src.AML_triage.core.report_generator import ReportGenerator, ReportGenerationError
    from src.AML_triage.core.validation import SchemaValidationError, hash_payload


router = APIRouter()

_TRIAGE_SETTINGS = load_settings()
_TRIAGE_GENERATOR = ReportGenerator(settings=_TRIAGE_SETTINGS)

_DECISION_MAP = {
    "pass": "PASS",
    "suspicious": "SUS",
    "fail": "FAIL",
}

_ACTION_MAP = {
    "PASS": ["CREATE_CASE"],
    "SUS": ["CREATE_CASE", "ESCALATE_L2_AML", "REQUEST_SOF_DOCS"],
    "FAIL": ["FILE_STR_DRAFT", "PLACE_SOFT_HOLD", "ESCALATE_L2_AML"],
}


def _to_iso3(code: Optional[str]) -> str:
    if not code:
        return "UNK"
    code = code.upper()
    if len(code) == 3:
        return code
    if len(code) == 2:
        return f"{code}X"
    return (code[:3]).ljust(3, "X")


@router.get("/sample")
async def get_sample_payment() -> Dict[str, Any]:
    """Return a random transaction from the dataset for demo purposes."""
    transaction = transaction_service.get_random_transaction()
    return transaction.model_dump()


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_payment_endpoint(payment: PaymentTransaction) -> Dict[str, Any]:
    """Run the single-payment analysis workflow and return the verdict payload."""
    payment_dict = payment.model_dump()
    payment_dict["payment_id"] = str(payment_dict.get("payment_id"))

    analysis_result = await analyze_payment(payment_dict)
    return analysis_result


@router.post("/analyze/stream")
async def analyze_payment_stream_endpoint(
    payment: PaymentTransaction,
    related_limit: int = 10,
    stream_duration_seconds: int = 30,
    message_count: int = 12,
) -> StreamingResponse:
    """
    Stream incremental analysis updates for a payment with related history.

    Emits:
        - analysis_started
        - related_transaction (for each match)
        - analysis_complete (with the final verdict)
    """
    if related_limit <= 0:
        related_limit = 10
    if message_count <= 0:
        message_count = 10
    interval = max(stream_duration_seconds / message_count, 0.5)

    payment_dict = payment.model_dump()
    payment_dict["payment_id"] = str(payment_dict.get("payment_id"))

    related_transactions = collect_related_transactions(payment_dict, limit=related_limit)
    rules = await rules_service.get_active_rules(jurisdiction=payment_dict.get("originator_country"))

    analysis_task = asyncio.create_task(
        generate_streaming_analysis(payment_dict, related_transactions, rules)
    )

    async def event_stream():
        start_message = {
            "event": "analysis_started",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payment_id": payment_dict.get("payment_id"),
            "related_count": len(related_transactions),
        }
        yield f"data: {json.dumps(start_message)}\n\n"

        for idx, tx in enumerate(related_transactions, start=1):
            payload = {
                "event": "related_transaction",
                "sequence": idx,
                "total": len(related_transactions),
                "transaction": {
                    "transaction_id": tx.transaction_id,
                    "booking_datetime": tx.booking_datetime.isoformat(),
                    "amount": float(tx.amount),
                    "currency": tx.currency,
                    "channel": tx.channel,
                    "product_type": tx.product_type,
                    "swift_mt": tx.swift_mt,
                    "purpose_code": tx.purpose_code,
                    "narrative": tx.narrative,
                    "sanctions_screening": tx.sanctions_screening,
                },
            }
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(interval)

        analysis_result = await analysis_task

        final_payload = {
            "event": "analysis_complete",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "payment_id": payment_dict.get("payment_id"),
            "verdict": analysis_result.get("verdict"),
            "risk_score": analysis_result.get("risk_score"),
            "assigned_team": analysis_result.get("assigned_team"),
            "narrative_summary": analysis_result.get("narrative_summary"),
            "rule_references": analysis_result.get("rule_references", []),
            "notable_transactions": analysis_result.get("notable_transactions", []),
            "recommended_actions": analysis_result.get("recommended_actions", []),
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class TriageRequest(BaseModel):
    payment: Dict[str, Any]  # Accept any dict to be flexible
    analysis: Dict[str, Any]


@router.post("/triage", status_code=status.HTTP_200_OK)
async def triage_payment(request: TriageRequest) -> Dict[str, Any]:
    """
    Submit an analyzed payment to the AML triage engine and return the generated report.
    """
    payment = request.payment
    analysis = request.analysis

    decision = _DECISION_MAP.get(str(analysis.get("verdict", "suspicious")).lower(), "SUS")

    # Extract rule codes from various possible formats
    triggered_rules = analysis.get("triggered_rules", [])
    rule_codes = []

    for rule in triggered_rules:
        if isinstance(rule, dict):
            # Try different field names
            code = (rule.get("rule_id") or
                   rule.get("rule_type") or
                   rule.get("pattern_type") or
                   rule.get("name"))
            if code:
                rule_codes.append(str(code))

    # Fallback to rule_references if no codes found
    if not rule_codes:
        rule_codes = analysis.get("rule_references", [])

    if not rule_codes:
        rule_codes = ["GENERIC_RULE"]

    action_ids = _ACTION_MAP.get(decision, ["action_manual_review"])

    corridor = {
        "origin_country": _to_iso3(payment.get("originator_country")),
        "destination_country": _to_iso3(payment.get("beneficiary_country")),
        "channel": payment.get("channel") or "unknown",
        "currency": (payment.get("currency") or "USD").upper(),
    }

    # Build comprehensive analysis report
    analysis_report_parts = [
        analysis.get("justification"),
        analysis.get("llm_summary"),
        analysis.get("narrative_summary"),
    ]
    analysis_report = "\n\n".join(part for part in analysis_report_parts if part)
    if not analysis_report:
        analysis_report = "No detailed analysis provided."

    # Add recommended actions to report
    recommended_actions = analysis.get("recommended_actions", [])
    if recommended_actions:
        analysis_report += "\n\n### Recommended Actions:\n"
        for action in recommended_actions:
            analysis_report += f"- {action}\n"

    behavioural_patterns = [
        pattern.get("pattern_type")
        for pattern in analysis.get("detected_patterns", [])
        if pattern.get("pattern_type")
    ] + [
        pattern.get("pattern_type")
        for pattern in analysis.get("llm_patterns", [])
        if isinstance(pattern, dict) and pattern.get("pattern_type")
    ]

    evidence = []
    for tx in analysis.get("llm_flagged_transactions", []):
        digest = hash_payload(tx)
        evidence.append({
            "type": "transaction",
            "id_hash": digest[:32],
            "summary": tx.get("reason"),
        })

    trace_id = analysis.get("trace_id") or "unknown"

    # Build ranked_actions from action_ids
    ranked_actions = [
        {
            "action_id": action_id,
            "confidence": 0.8,
            "for_signals": rule_codes,
            "template_tags": behavioural_patterns[:3]  # Limit to top 3
        }
        for action_id in action_ids
    ]

    screening_result = {
        "schema": "llm3_triage",
        "schema_version": _TRIAGE_SETTINGS.schema_version,
        "trace_id": trace_id,
        "decision": decision,
        "rule_codes": rule_codes,
        "action_ids": action_ids,
        "ranked_actions": ranked_actions,
        "analysis_report": analysis_report,
        "corridor": corridor,
        "amount": float(payment.get("amount", 0.0)),
        "behavioural_patterns": behavioural_patterns,
        "evidence": evidence,
        "metadata": {
            "payment_id": payment.get("payment_id") or payment.get("transaction_id"),
            "trace_id": trace_id,
        },
    }

    try:
        plan_text = await _TRIAGE_GENERATOR.generate_report(screening_result)
    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors}) from exc
    except ReportGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "screening_result": screening_result,
        "triage_plan": plan_text,
    }
