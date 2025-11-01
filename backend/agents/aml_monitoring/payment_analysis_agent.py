"""
Payment Analysis Agent - Main LangGraph workflow orchestrator.
Coordinates rule checking, pattern detection, and verdict calculation.
"""
import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from uuid import uuid4

from langgraph.graph import StateGraph, END

try:
    # Try backend-prefixed imports first (running from parent directory)
    from backend.core.observability import get_logger
    from backend.core.config import settings
    from backend.agents.aml_monitoring.state_schemas import PaymentAnalysisState
    from backend.agents.aml_monitoring.rule_checker_agent import check_rules_node
    from backend.agents.aml_monitoring.verdict_router import calculate_verdict_node
    from backend.agents.aml_monitoring.risk_analyzer import run_risk_analysis
    from backend.models.query_params import QueryParameters
    from backend.models.transaction import TransactionRecord
    from backend.services.transaction_service import transaction_service
    from backend.services.rules_service import rules_service
    from backend.services.llm_client import grok_client
except ModuleNotFoundError:
    # Fall back to relative imports (running from backend directory)
    from core.observability import get_logger
    from core.config import settings
    from agents.aml_monitoring.state_schemas import PaymentAnalysisState
    from agents.aml_monitoring.rule_checker_agent import check_rules_node
    from agents.aml_monitoring.verdict_router import calculate_verdict_node
    from agents.aml_monitoring.risk_analyzer import run_risk_analysis
    from models.query_params import QueryParameters
    from models.transaction import TransactionRecord
    from services.transaction_service import transaction_service
    from services.rules_service import rules_service
    from services.llm_client import grok_client

logger = get_logger(__name__)

# ============================================================================
# Pattern Detection Node
# ============================================================================

async def detect_patterns_node(state: PaymentAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node: Detect AML patterns in historical transactions.

    Analyzes payment history to identify:
    - Structuring (multiple transactions below threshold)
    - Velocity anomalies (unusual transaction frequency)
    - Round-tripping (circular money flow)
    - Layering (complex transaction chains)

    Args:
        state: Current PaymentAnalysisState from LangGraph workflow

    Returns:
        Dict with detected_patterns and pattern_score updates
    """
    payment = state["payment"]
    historical_transactions = state["historical_transactions"]
    trace_id = state["trace_id"]

    logger.info(
        f"pattern_detection_started - trace_id={trace_id}, historical_count={len(historical_transactions)}"
    )

    detected_patterns = []

    # Pattern 1: Structuring detection
    structuring_pattern = _detect_structuring(payment, historical_transactions)
    if structuring_pattern:
        detected_patterns.append(structuring_pattern)

    # Pattern 2: Velocity anomalies
    velocity_pattern = _detect_velocity_anomaly(payment, historical_transactions)
    if velocity_pattern:
        detected_patterns.append(velocity_pattern)

    # Pattern 3: High-risk jurisdiction patterns
    jurisdiction_pattern = _detect_jurisdiction_risk(payment)
    if jurisdiction_pattern:
        detected_patterns.append(jurisdiction_pattern)

    # Calculate aggregate pattern score
    pattern_score = _calculate_pattern_score(detected_patterns)

    logger.info(
        f"pattern_detection_completed - trace_id={trace_id}, detected_patterns_count={len(detected_patterns)}, pattern_score={pattern_score}"
    )

    return {
        "detected_patterns": detected_patterns,
        "pattern_score": pattern_score
    }


def _detect_structuring(
    payment: Dict[str, Any],
    historical_transactions: list[Dict[str, Any]]
) -> Dict[str, Any] | None:
    """
    Detect structuring: Multiple transactions below reporting threshold.

    Args:
        payment: Current payment transaction
        historical_transactions: Historical payment data

    Returns:
        Pattern dict if detected, None otherwise
    """
    threshold = settings.structuring_threshold  # e.g., 10000
    current_amount = payment.get("amount", 0)

    # Check if current transaction is below threshold
    if current_amount >= threshold:
        return None

    # Count recent transactions below threshold from same originator
    originator = payment.get("originator_account")
    recent_below_threshold = [
        tx for tx in historical_transactions
        if tx.get("originator_account") == originator
        and tx.get("amount", 0) < threshold
    ]

    # Structuring if 3+ transactions below threshold in short period
    if len(recent_below_threshold) >= 3:
        total_amount = sum(tx.get("amount", 0) for tx in recent_below_threshold)
        return {
            "pattern_type": "structuring",
            "description": f"Potential structuring: {len(recent_below_threshold)} transactions totaling {total_amount}",
            "severity": "high",
            "confidence": 0.8,
            "pattern_score": 35.0
        }

    return None
#
# ============================================================================
# LLM Assessment Node
# ============================================================================



def _build_current_payment_context(payment: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant payment fields for LLM analysis."""
    return {
        "payment_id": str(payment.get("payment_id", "")),
        "booking_datetime": payment.get("transaction_date"),
        "value_date": payment.get("value_date"),
        "originator_name": payment.get("originator_name"),
        "originator_account": payment.get("originator_account"),
        "originator_country": payment.get("originator_country"),
        "beneficiary_name": payment.get("beneficiary_name"),
        "beneficiary_account": payment.get("beneficiary_account"),
        "beneficiary_country": payment.get("beneficiary_country"),
        "amount": payment.get("amount"),
        "currency": payment.get("currency"),
        "channel": payment.get("channel"),
        "product_type": payment.get("product_type"),
        "swift_mt": payment.get("swift_message_type"),
        "purpose_code": payment.get("purpose_code"),
        "narrative": payment.get("narrative"),
        "sanctions_screening_result": payment.get("sanctions_screening_result"),
        "edd_required": payment.get("edd_required"),
        "edd_performed": payment.get("edd_performed"),
        "str_filed_datetime": payment.get("str_filed_datetime"),
        "client_risk_profile": payment.get("client_risk_profile"),
        "customer_risk_profile": payment.get("customer_risk_profile", payment.get("customer_risk_rating")),
    }

async def llm_assessment_node(state: PaymentAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node: Run LLM risk analysis over historical transactions and rules.
    """
    payment = state["payment"]
    trace_id = state["trace_id"]
    historical_transactions = state.get("historical_transactions", [])

    if not historical_transactions:
        logger.info(
            "llm_assessment_skipped - trace_id=%s (no historical transactions)",
            trace_id,
        )
        return {
            "llm_risk_score": 0.0,
            "llm_summary": "Insufficient transaction history for LLM assessment.",
            "llm_flagged_transactions": [],
            "llm_patterns": [],
        }

    try:
        # Convert history dicts back to TransactionRecord objects
        transaction_records = []
        for tx_data in historical_transactions:
            try:
                transaction_records.append(TransactionRecord.model_validate(tx_data))
            except Exception as exc:
                logger.warning(
                    "llm_transaction_parse_failed - trace_id=%s, transaction_id=%s, error=%s",
                    trace_id,
                    tx_data.get("transaction_id"),
                    str(exc),
                )

        if not transaction_records:
            logger.warning(
                "llm_assessment_skipped - trace_id=%s (unable to parse transactions)",
                trace_id,
            )
            return {
                "llm_risk_score": 0.0,
                "llm_summary": "Unable to parse historical transactions for LLM assessment.",
                "llm_flagged_transactions": [],
                "llm_patterns": [],
            }

        # Limit transactions to most recent 50 to control prompt size
        transaction_records.sort(key=lambda tx: tx.booking_datetime, reverse=True)
        transaction_records = transaction_records[:50]

        # Fetch compliance rules for jurisdiction
        jurisdiction = payment.get("originator_country")
        compliance_rules = []
        if jurisdiction:
            rules = await rules_service.get_active_rules(jurisdiction=jurisdiction)
            compliance_rules = [
                _serialize_compliance_rule(rule)
                for rule in rules[:25]
            ]

        current_payment_context = _build_current_payment_context(payment)

        analysis_result = await run_risk_analysis(
            transactions=transaction_records,
            rules_data=None,
            compliance_rules=compliance_rules,
            current_payment=current_payment_context,
        )

        llm_risk = analysis_result.overall_risk_score or 0.0
        llm_score = float(llm_risk) * 10.0  # Convert 0-10 scale to 0-100
        summary = analysis_result.narrative_summary or ""
        flagged = [ft.model_dump() for ft in analysis_result.flagged_transactions]
        patterns = [pt.model_dump() for pt in analysis_result.identified_patterns]

        logger.info(
            "llm_assessment_completed - trace_id=%s, llm_score=%s, flagged=%s",
            trace_id,
            llm_score,
            len(flagged),
        )

        return {
            "llm_risk_score": min(llm_score, 100.0),
            "llm_summary": summary,
            "llm_flagged_transactions": flagged,
            "llm_patterns": patterns,
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "llm_assessment_failed - trace_id=%s, error=%s",
            trace_id,
            str(exc),
            exc_info=True,
        )
        return {
            "llm_risk_score": 0.0,
            "llm_summary": f"LLM assessment failed: {str(exc)}",
            "llm_flagged_transactions": [],
            "llm_patterns": [],
            "errors": state.get("errors", []) + [f"LLM assessment failed: {str(exc)}"],
        }


def _detect_velocity_anomaly(
    payment: Dict[str, Any],
    historical_transactions: list[Dict[str, Any]]
) -> Dict[str, Any] | None:
    """
    Detect velocity anomaly: Unusual transaction frequency.

    Args:
        payment: Current payment transaction
        historical_transactions: Historical payment data

    Returns:
        Pattern dict if detected, None otherwise
    """
    # Simple velocity check: more than 10 transactions in recent history
    if len(historical_transactions) > 10:
        return {
            "pattern_type": "velocity_anomaly",
            "description": f"High transaction velocity: {len(historical_transactions)} recent transactions",
            "severity": "medium",
            "confidence": 0.7,
            "pattern_score": 25.0
        }

    return None


def _detect_jurisdiction_risk(payment: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Detect high-risk jurisdiction involvement.

    Args:
        payment: Current payment transaction

    Returns:
        Pattern dict if detected, None otherwise
    """
    high_risk_countries = settings.high_risk_jurisdictions_list
    originator_country = payment.get("originator_country")
    beneficiary_country = payment.get("beneficiary_country")

    if originator_country in high_risk_countries or beneficiary_country in high_risk_countries:
        return {
            "pattern_type": "high_risk_jurisdiction",
            "description": f"Transaction involves high-risk jurisdiction: {originator_country} -> {beneficiary_country}",
            "severity": "high",
            "confidence": 0.9,
            "pattern_score": 30.0
        }

    return None


def _calculate_pattern_score(detected_patterns: list[Dict[str, Any]]) -> float:
    """
    Calculate aggregate pattern score.

    Args:
        detected_patterns: List of detected patterns

    Returns:
        Aggregate score (0-100)
    """
    if not detected_patterns:
        return 0.0

    # Sum pattern scores with confidence weighting
    total_score = sum(
        p["pattern_score"] * p.get("confidence", 1.0)
        for p in detected_patterns
    )

    # Cap at 100
    return min(total_score, 100.0)

# ============================================================================
# Data Fetch Node
# ============================================================================

async def fetch_history_node(state: PaymentAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node: Fetch historical transaction data.

    Retrieves payment history from feature 001 for pattern analysis.

    Args:
        state: Current PaymentAnalysisState from LangGraph workflow

    Returns:
        Dict with historical_transactions update
    """
    payment = state["payment"]
    trace_id = state["trace_id"]

    logger.info(f"history_fetch_started - trace_id={trace_id}")

    params = QueryParameters(
        originator_name=payment.get("originator_name"),
        originator_account=payment.get("originator_account"),
        beneficiary_name=payment.get("beneficiary_name"),
        beneficiary_account=payment.get("beneficiary_account"),
    )

    historical_transactions: List[TransactionRecord] = []
    try:
        if params.has_filters:
            history = transaction_service.query(params)
            historical_transactions = history.transactions
        else:
            logger.info("No query filters provided, skipping history lookup")
    except Exception as exc:
        logger.warning(
            "history_fetch_failed - trace_id=%s, error=%s",
            trace_id,
            str(exc),
        )
        historical_transactions = []

    logger.info(
        "history_fetch_completed - trace_id=%s, historical_count=%s",
        trace_id,
        len(historical_transactions),
    )

    return {
        "historical_transactions": [
            tx.model_dump(mode="python")
            for tx in historical_transactions
        ]
    }


# ============================================================================
# Helpers for streaming assessment
# ============================================================================


def _json_serializer(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_payment_for_prompt(payment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "payment_id": str(payment.get("payment_id", "")),
        "booking_datetime": payment.get("transaction_date"),
        "value_date": payment.get("value_date"),
        "originator_name": payment.get("originator_name"),
        "originator_account": payment.get("originator_account"),
        "originator_country": payment.get("originator_country"),
        "beneficiary_name": payment.get("beneficiary_name"),
        "beneficiary_account": payment.get("beneficiary_account"),
        "beneficiary_country": payment.get("beneficiary_country"),
        "amount": payment.get("amount"),
        "currency": payment.get("currency"),
        "channel": payment.get("channel"),
        "product_type": payment.get("product_type"),
        "swift_mt": payment.get("swift_message_type"),
        "purpose_code": payment.get("purpose_code"),
        "narrative": payment.get("narrative"),
        "sanctions_screening_result": payment.get("sanctions_screening_result"),
        "edd_required": payment.get("edd_required"),
        "edd_performed": payment.get("edd_performed"),
        "str_filed_datetime": payment.get("str_filed_datetime"),
        "client_risk_profile": payment.get("client_risk_profile"),
        "customer_risk_rating": payment.get("customer_risk_rating"),
    }


def _serialize_history_record(tx: TransactionRecord) -> Dict[str, Any]:
    return {
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
        "edd_required": tx.edd_required,
        "edd_performed": tx.edd_performed,
        "str_filed_datetime": tx.str_filed_datetime.isoformat() if tx.str_filed_datetime else None,
        "client_risk_profile": tx.client_risk_profile,
        "customer_risk_rating": tx.customer_risk_rating,
    }


def _serialize_compliance_rule(rule: Any) -> Dict[str, Any]:
    return {
        "rule_id": str(rule.rule_id),
        "rule_type": rule.rule_type,
        "severity": rule.severity,
        "description": rule.description,
        "jurisdiction": rule.jurisdiction,
        "regulator": rule.regulator,
        "rule_data": rule.rule_data,
    }


def collect_related_transactions(payment: Dict[str, Any], limit: int = 10) -> List[TransactionRecord]:
    booking_dt = payment.get("transaction_date")
    booking_str = None
    if isinstance(booking_dt, datetime):
        booking_str = booking_dt.isoformat()
    elif isinstance(booking_dt, str):
        booking_str = booking_dt

    params = QueryParameters(
        originator_name=payment.get("originator_name"),
        originator_account=payment.get("originator_account"),
        beneficiary_name=payment.get("beneficiary_name"),
        beneficiary_account=payment.get("beneficiary_account"),
        booking_datetime=booking_str,
    )

    if not params.has_filters:
        return []

    history = transaction_service.query(params)
    records = sorted(history.transactions, key=lambda tx: tx.booking_datetime, reverse=True)
    if limit > 0:
        records = records[:limit]
    return records


async def generate_streaming_analysis(
    payment: Dict[str, Any],
    related_history: List[TransactionRecord],
    rules: List[Any]
) -> Dict[str, Any]:
    current_payment = _serialize_payment_for_prompt(payment)
    history_payload = [_serialize_history_record(tx) for tx in related_history]
    rules_payload = [_serialize_compliance_rule(rule) for rule in rules[:50]]

    prompt_context = {
        "current_payment": current_payment,
        "related_history": history_payload,
        "compliance_rules": rules_payload,
    }

    prompt = f"""# Streaming AML Risk Assessment

Evaluate the target payment in the context of the related transaction history and compliance rules provided.

## Current Payment
```json
{json.dumps(prompt_context['current_payment'], indent=2, default=_json_serializer)}
```

## Related History (most recent first)
```json
{json.dumps(prompt_context['related_history'], indent=2, default=_json_serializer)}
```

## Active Compliance Rules
```json
{json.dumps(prompt_context['compliance_rules'], indent=2, default=_json_serializer)}
```

### Output Requirements
Return valid JSON with the following structure:
{{
  "verdict": "pass" | "suspicious" | "fail",
  "risk_score": <float 0-100>,
  "assigned_team": "front_office" | "compliance" | "legal",
  "narrative_summary": "<concise explanation>",
  "rule_references": ["..."],
  "notable_transactions": [
    {{
      "transaction_id": "...",
      "reason": "..."
    }}
  ],
  "recommended_actions": ["..."]
}}

Focus on the specified fields: amount, currency, channel, product_type, swift_mt, purpose_code, narrative,
sanctions_screening, edd_required, edd_performed, str_filed_datetime, client_risk_profile, customer_risk_profile.
"""

    transactions_payload = [current_payment] + history_payload
    llm_response = await grok_client.analyze_transactions(transactions_payload, prompt)

    if isinstance(llm_response, str):
        llm_response = json.loads(llm_response)

    return llm_response

# ============================================================================
# LangGraph Workflow Builder
# ============================================================================

def build_payment_analysis_graph() -> StateGraph:
    """
    Build the LangGraph StateGraph for payment analysis workflow.

    Workflow:
    1. fetch_history_node: Retrieve historical transactions from CSV
    2. check_rules_node: Evaluate compliance rules
    3. detect_patterns_node: Analyze historical patterns
    4. llm_assessment_node: Run LLM-based risk assessment using rules + history
    5. calculate_verdict_node: Determine final verdict and team assignment

    Returns:
        Compiled StateGraph ready for execution
    """
    # Create graph with PaymentAnalysisState schema
    workflow = StateGraph(PaymentAnalysisState)

    # Add nodes
    workflow.add_node("fetch_history", fetch_history_node)
    workflow.add_node("check_rules", check_rules_node)
    workflow.add_node("detect_patterns", detect_patterns_node)
    workflow.add_node("llm_assessment", llm_assessment_node)
    workflow.add_node("calculate_verdict", calculate_verdict_node)

    # Define edges (workflow flow - sequential to avoid multiple edge issue)
    workflow.set_entry_point("fetch_history")
    workflow.add_edge("fetch_history", "check_rules")
    workflow.add_edge("check_rules", "detect_patterns")
    workflow.add_edge("detect_patterns", "llm_assessment")
    workflow.add_edge("llm_assessment", "calculate_verdict")
    workflow.add_edge("calculate_verdict", END)

    return workflow.compile()

# ============================================================================
# Public API
# ============================================================================

async def analyze_payment(payment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a payment transaction for AML risk.

    This is the main entry point for payment analysis. It initializes
    the LangGraph state and executes the workflow.

    Args:
        payment: Payment transaction data (dict representation of PaymentTransaction)

    Returns:
        Analysis result with verdict, risk_score, triggered_rules, etc.
    """
    # Initialize state
    trace_id = uuid4()
    payment_id = payment.get("payment_id", str(uuid4()))
    analysis_start_time = time.time()

    initial_state: PaymentAnalysisState = {
        "payment": payment,
        "payment_id": payment_id,
        "trace_id": trace_id,
        "historical_transactions": [],
        "triggered_rules": [],
        "detected_patterns": [],
        "llm_flagged_transactions": [],
        "llm_patterns": [],
        "rule_score": 0.0,
        "pattern_score": 0.0,
        "risk_score": 0.0,
        "llm_risk_score": 0.0,
        "verdict": "pass",
        "assigned_team": "front_office",
        "justification": "",
        "llm_summary": "",
        "analysis_start_time": analysis_start_time,
        "analysis_duration_ms": 0,
        "llm_model": settings.llm_model,
        "errors": []
    }

    logger.info(f"payment_analysis_started - trace_id={trace_id}, payment_id={payment_id}")

    try:
        # Build and execute workflow
        graph = build_payment_analysis_graph()
        final_state = await graph.ainvoke(initial_state)

        # Calculate duration
        analysis_duration_ms = int((time.time() - analysis_start_time) * 1000)
        final_state["analysis_duration_ms"] = analysis_duration_ms

        logger.info(
            f"payment_analysis_completed - trace_id={trace_id}, verdict={final_state['verdict']}, "
            f"risk_score={final_state['risk_score']}, duration_ms={analysis_duration_ms}"
        )

        return final_state

    except Exception as e:
        logger.error(f"payment_analysis_failed - trace_id={trace_id}, error={str(e)}")
        raise
"""
Payment analysis agent functions for single-payment workflow.
"""

import logging
from typing import Any, Dict, List
from services.llm_client import grok_client
from services.transaction_service import transaction_service

logger = logging.getLogger(__name__)


async def analyze_payment(payment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a single payment and return verdict.

    Args:
        payment: Payment transaction dictionary

    Returns:
        Analysis result with verdict, risk_score, etc.
    """
    logger.info(f"Analyzing payment: {payment.get('payment_id')}")

    # Build analysis prompt
    prompt = f"""
Analyze this payment transaction for AML risks:

Transaction ID: {payment.get('transaction_id')}
Amount: {payment.get('amount')} {payment.get('currency')}
Originator: {payment.get('originator_name')} ({payment.get('originator_country')})
Beneficiary: {payment.get('beneficiary_name')} ({payment.get('beneficiary_country')})
Channel: {payment.get('channel')}
Purpose: {payment.get('purpose_code')}
Narrative: {payment.get('narrative')}

Provide a JSON response with:
{{
  "verdict": "pass|suspicious|fail",
  "risk_score": <0-100>,
  "justification": "<explanation>",
  "assigned_team": "<team_name>",
  "narrative_summary": "<summary>",
  "rule_references": ["<rule_codes>"],
  "notable_transactions": [],
  "recommended_actions": ["<actions>"],
  "triggered_rules": [],
  "detected_patterns": [],
  "llm_patterns": [],
  "llm_flagged_transactions": []
}}
"""

    result = await grok_client.analyze_transactions([payment], prompt)
    return result


def collect_related_transactions(payment: Dict[str, Any], limit: int = 10) -> List[Any]:
    """
    Collect related transactions for a payment.

    Args:
        payment: Payment transaction dictionary
        limit: Maximum number of related transactions

    Returns:
        List of related TransactionRecord objects
    """
    logger.info(f"Collecting up to {limit} related transactions")

    # Try to find related transactions by originator account
    originator_account = payment.get('originator_account')
    if originator_account:
        transactions = transaction_service.get_transactions_by_account(
            originator_account,
            limit=limit
        )
        return transactions

    return []


async def generate_streaming_analysis(
    payment: Dict[str, Any],
    related_transactions: List[Any],
    rules: Any
) -> Dict[str, Any]:
    """
    Generate analysis for streaming endpoint.

    Args:
        payment: Payment transaction dictionary
        related_transactions: List of related transactions
        rules: Active rules data

    Returns:
        Analysis result dictionary
    """
    logger.info(f"Generating streaming analysis with {len(related_transactions)} related txns")

    # Build comprehensive prompt with related transactions
    related_summaries = [
        f"- {tx.transaction_id}: {tx.amount} {tx.currency} via {tx.channel}"
        for tx in related_transactions[:5]
    ]

    prompt = f"""
Analyze this payment with historical context:

Main Transaction:
- ID: {payment.get('transaction_id')}
- Amount: {payment.get('amount')} {payment.get('currency')}
- Originator: {payment.get('originator_name')} ({payment.get('originator_country')})
- Beneficiary: {payment.get('beneficiary_name')} ({payment.get('beneficiary_country')})

Related Transactions ({len(related_transactions)}):
{chr(10).join(related_summaries)}

Provide a JSON response with:
{{
  "verdict": "pass|suspicious|fail",
  "risk_score": <0-100>,
  "justification": "<explanation>",
  "assigned_team": "<team_name>",
  "narrative_summary": "<summary>",
  "rule_references": ["<rule_codes>"],
  "notable_transactions": [],
  "recommended_actions": ["<actions>"]
}}
"""

    result = await grok_client.analyze_transactions([payment], prompt)
    return result
