"""
Payment Analysis Router - FastAPI endpoints for payment analysis.
Provides REST API for analyzing payments and retrieving verdicts/alerts.
"""
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from uuid import UUID
from typing import Optional

try:
    # Try backend-prefixed imports first (running from parent directory)
    from backend.core.observability import get_logger, payment_analysis_total, analysis_latency_ms
    from backend.models.payment import PaymentTransaction
    from backend.agents.aml_monitoring.payment_analysis_agent import (
        analyze_payment,
        collect_related_transactions,
        generate_streaming_analysis,
    )
    from backend.services.transaction_service import transaction_service
    from backend.services.rules_service import rules_service
    from backend.services.verdict_service import verdict_service
    from backend.services.alert_service import alert_service
    from backend.services.audit_service import audit_service
except ModuleNotFoundError:
    # Fall back to relative imports (running from backend directory)
    from core.observability import get_logger, payment_analysis_total, analysis_latency_ms
    from models.payment import PaymentTransaction
    from agents.aml_monitoring.payment_analysis_agent import (
        analyze_payment,
        collect_related_transactions,
        generate_streaming_analysis,
    )
    from services.transaction_service import transaction_service
    from services.rules_service import rules_service
    from services.verdict_service import verdict_service
    from services.alert_service import alert_service
    from services.audit_service import audit_service

logger = get_logger(__name__)

router = APIRouter()


@router.get("/sample", status_code=status.HTTP_200_OK)
async def get_sample_payment():
    """Return a random payment from the dataset for demo purposes."""
    transaction = transaction_service.get_random_transaction()
    return transaction.model_dump()


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_payment_endpoint(payment: PaymentTransaction):
    """
    Analyze a payment transaction for AML risk.

    This endpoint:
    1. Runs the payment through the LangGraph analysis workflow
    2. Saves the verdict to the database
    3. Creates an alert if needed (for suspicious/fail verdicts)
    4. Returns the complete analysis result

    Args:
        payment: Payment transaction data

    Returns:
        Analysis result with verdict, risk scores, triggered rules, etc.
    """
    logger.info(
        f"payment_analysis_request - payment_id={payment.payment_id}, amount={payment.amount}, currency={payment.currency}"
    )

    try:
        # Convert Pydantic model to dict for LangGraph
        payment_dict = payment.model_dump()

        # Run analysis through LangGraph workflow
        analysis_result = await analyze_payment(payment_dict)

        # Save verdict to database
        verdict_id = await verdict_service.save_verdict(
            payment_id=analysis_result["payment_id"],
            trace_id=analysis_result["trace_id"],
            verdict=analysis_result["verdict"],
            assigned_team=analysis_result["assigned_team"],
            risk_score=analysis_result["risk_score"],
            rule_score=analysis_result["rule_score"],
            pattern_score=analysis_result["pattern_score"],
            justification=analysis_result["justification"],
            triggered_rules=analysis_result["triggered_rules"],
            detected_patterns=analysis_result["detected_patterns"],
            analysis_duration_ms=analysis_result["analysis_duration_ms"],
            llm_model=analysis_result["llm_model"]
        )

        # Create alert if needed (suspicious or fail)
        alert_id = None
        if analysis_result["verdict"] in ["suspicious", "fail"]:
            alert_id = await alert_service.create_alert(
                payment_id=analysis_result["payment_id"],
                verdict_id=verdict_id,
                trace_id=analysis_result["trace_id"],
                verdict=analysis_result["verdict"],
                assigned_team=analysis_result["assigned_team"],
                risk_score=analysis_result["risk_score"],
                triggered_rules=analysis_result["triggered_rules"],
                detected_patterns=analysis_result["detected_patterns"],
                justification=analysis_result["justification"]
            )

        # Log to audit trail
        await audit_service.log_analysis_decision(
            trace_id=analysis_result["trace_id"],
            payment_id=analysis_result["payment_id"],
            action="payment_analysis",
            verdict=analysis_result["verdict"],
            assigned_team=analysis_result["assigned_team"],
            risk_score=analysis_result["risk_score"],
            decision_rationale=analysis_result["justification"],
            triggered_rules_count=len(analysis_result["triggered_rules"]),
            detected_patterns_count=len(analysis_result["detected_patterns"]),
            analysis_duration_ms=analysis_result["analysis_duration_ms"],
            llm_model=analysis_result["llm_model"],
            metadata={
                "rule_score": analysis_result["rule_score"],
                "pattern_score": analysis_result["pattern_score"],
                "alert_created": alert_id is not None
            }
        )

        # Update Prometheus metrics
        payment_analysis_total.labels(
            verdict=analysis_result["verdict"],
            team=analysis_result["assigned_team"]
        ).inc()
        analysis_latency_ms.observe(analysis_result["analysis_duration_ms"])

        logger.info(
            f"payment_analysis_completed - payment_id={payment.payment_id}, verdict={analysis_result['verdict']}, "
            f"risk_score={analysis_result['risk_score']}, alert_created={alert_id is not None}"
        )

        # Return response
        return {
            "payment_id": str(analysis_result["payment_id"]),
            "trace_id": str(analysis_result["trace_id"]),
            "verdict": analysis_result["verdict"],
            "assigned_team": analysis_result["assigned_team"],
            "risk_score": analysis_result["risk_score"],
            "rule_score": analysis_result["rule_score"],
            "pattern_score": analysis_result["pattern_score"],
            "llm_risk_score": analysis_result.get("llm_risk_score", 0.0),
            "justification": analysis_result["justification"],
            "triggered_rules": analysis_result["triggered_rules"],
            "detected_patterns": analysis_result["detected_patterns"],
            "llm_flagged_transactions": analysis_result.get("llm_flagged_transactions", []),
            "llm_patterns": analysis_result.get("llm_patterns", []),
            "llm_summary": analysis_result.get("llm_summary", ""),
            "analysis_duration_ms": analysis_result["analysis_duration_ms"],
            "alert_id": str(alert_id) if alert_id else None,
            "verdict_id": str(verdict_id)
        }

    except Exception as e:
        logger.error(
            f"payment_analysis_failed - payment_id={payment.payment_id}, error={str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment analysis failed: {str(e)}"
        )


@router.post("/analyze/stream")
async def analyze_payment_stream_endpoint(
    payment: PaymentTransaction,
    related_limit: int = 10,
    stream_duration_seconds: int = 30,
    message_count: int = 12,
):
    """Stream incremental analysis updates for a payment with related history."""

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

@router.get("/verdicts/{payment_id}")
async def get_verdict(payment_id: UUID):
    """
    Retrieve verdict for a payment transaction.

    Args:
        payment_id: Payment transaction ID

    Returns:
        Verdict details
    """
    logger.info(f"verdict_lookup - payment_id={payment_id}")

    verdict = await verdict_service.get_verdict_by_payment_id(payment_id)

    if not verdict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verdict not found for payment {payment_id}"
        )

    return verdict


@router.get("/alerts")
async def get_alerts(
    team: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """
    Get alerts with optional filtering.

    Query Parameters:
        team: Filter by assigned team (front_office/compliance/legal)
        status: Filter by status (pending/in_progress/resolved)
        limit: Maximum number of alerts to return (default 50)

    Returns:
        List of alerts
    """
    logger.info(f"alerts_lookup - team={team}, status={status}, limit={limit}")

    if team:
        alerts = await alert_service.get_alerts_by_team(
            team=team,
            status=status,
            limit=limit
        )
    else:
        # TODO: Implement get_all_alerts method
        alerts = []

    return {
        "alerts": alerts,
        "count": len(alerts)
    }


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: UUID):
    """
    Retrieve a specific alert by ID.

    Args:
        alert_id: Alert ID

    Returns:
        Alert details
    """
    logger.info(f"alert_lookup - alert_id={alert_id}")

    alert = await alert_service.get_alert(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}"
        )

    return alert


@router.patch("/alerts/{alert_id}/status")
async def update_alert_status(
    alert_id: UUID,
    status: str,
    investigation_notes: Optional[str] = None
):
    """
    Update alert status and investigation notes.

    Args:
        alert_id: Alert ID
        status: New status (pending/in_progress/resolved/false_positive)
        investigation_notes: Optional investigation notes

    Returns:
        Updated alert
    """
    logger.info(f"alert_status_update - alert_id={alert_id}, status={status}")

    # Validate status
    valid_statuses = ["pending", "in_progress", "resolved", "false_positive"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    success = await alert_service.update_alert_status(
        alert_id=alert_id,
        status=status,
        investigation_notes=investigation_notes
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert not found: {alert_id}"
        )

    return {"message": "Alert status updated successfully"}


@router.get("/stats/pending-alerts")
async def get_pending_alerts_count(team: Optional[str] = None):
    """
    Get count of pending alerts.

    Query Parameters:
        team: Optional team filter

    Returns:
        Pending alerts count
    """
    count = await alert_service.get_pending_alerts_count(team=team)

    return {
        "pending_alerts": count,
        "team": team or "all"
    }
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


router = APIRouter(prefix="/api/v1/payments", tags=["Payment Analysis"])

_TRIAGE_SETTINGS = load_settings()
_TRIAGE_GENERATOR = ReportGenerator(settings=_TRIAGE_SETTINGS)

_DECISION_MAP = {
    "pass": "PASS",
    "suspicious": "SUS",
    "fail": "FAIL",
}

_ACTION_MAP = {
    "PASS": ["action_release"],
    "SUS": ["action_manual_review"],
    "FAIL": ["action_freeze"],
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
    payment: PaymentTransaction
    analysis: Dict[str, Any]


@router.post("/triage", status_code=status.HTTP_200_OK)
async def triage_payment(request: TriageRequest) -> Dict[str, Any]:
    """
    Submit an analyzed payment to the AML triage engine and return the generated report.
    """
    payment = request.payment.model_dump()
    analysis = request.analysis

    decision = _DECISION_MAP.get(str(analysis.get("verdict", "suspicious")).lower(), "SUS")
    rule_codes = [
        str(rule.get("rule_id") or rule.get("rule_type"))
        for rule in analysis.get("triggered_rules", [])
    ] or analysis.get("rule_references", [])
    if not rule_codes:
        rule_codes = ["GENERIC_RULE"]

    action_ids = _ACTION_MAP.get(decision, ["action_manual_review"])

    corridor = {
        "origin_country": _to_iso3(payment.get("originator_country")),
        "destination_country": _to_iso3(payment.get("beneficiary_country")),
        "channel": payment.get("channel") or "unknown",
        "currency": (payment.get("currency") or "USD").upper(),
    }

    analysis_report_parts = [
        analysis.get("justification"),
        analysis.get("llm_summary"),
        analysis.get("narrative_summary"),
    ]
    analysis_report = "\n\n".join(part for part in analysis_report_parts if part)
    if not analysis_report:
        analysis_report = "No detailed analysis provided."

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

    screening_result = {
        "schema_version": _TRIAGE_SETTINGS.schema_version,
        "decision": decision,
        "rule_codes": rule_codes,
        "action_ids": action_ids,
        "analysis_report": analysis_report,
        "corridor": corridor,
        "amount": float(payment.get("amount", 0.0)),
        "behavioural_patterns": behavioural_patterns,
        "evidence": evidence,
        "metadata": {
            "payment_id": payment.get("payment_id"),
            "trace_id": analysis.get("trace_id"),
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
