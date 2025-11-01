"""
Rule Checker Agent - LangGraph node for checking compliance rules.
Evaluates payment transactions against active AML/CFT rules.
"""
from typing import Dict, Any, List

try:
    # Try backend-prefixed imports first (running from parent directory)
    from backend.core.config import settings
    from backend.core.observability import get_logger
    from backend.services.rules_service import rules_service
    from backend.agents.aml_monitoring.state_schemas import PaymentAnalysisState
except ModuleNotFoundError:
    # Fall back to relative imports (running from backend directory)
    from core.config import settings
    from core.observability import get_logger
    from services.rules_service import rules_service
    from agents.aml_monitoring.state_schemas import PaymentAnalysisState

logger = get_logger(__name__)


async def check_rules_node(state: PaymentAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node: Check payment against compliance rules.

    Queries active rules from feature 003 and evaluates the payment
    transaction against each rule to identify violations.

    Args:
        state: Current PaymentAnalysisState from LangGraph workflow

    Returns:
        Dict with triggered_rules and rule_score updates
    """
    payment = state["payment"]
    trace_id = state["trace_id"]

    logger.info(f"rule_check_started - trace_id={trace_id}, payment_id={state['payment_id']}")

    try:
        # Get active rules for this jurisdiction/regulator
        jurisdiction = payment.get("originator_country")
        rules = await rules_service.get_active_rules(jurisdiction=jurisdiction)

        triggered_rules: List[Dict[str, Any]] = []

        # Evaluate each rule against the payment
        for rule in rules:
            violation = await _evaluate_rule(payment, rule)
            if violation:
                triggered_rules.append({
                    "rule_id": str(rule.rule_id),
                    "rule_type": rule.rule_type,
                    "description": rule.description,
                    "severity": rule.severity,
                    "violation_details": violation["details"],
                    "severity_score": _severity_to_score(rule.severity)
                })

        # Calculate aggregate rule score (0-100)
        rule_score = _calculate_rule_score(triggered_rules)

        logger.info(
            f"rule_check_completed - trace_id={trace_id}, triggered_rules_count={len(triggered_rules)}, rule_score={rule_score}"
        )

        return {
            "triggered_rules": triggered_rules,
            "rule_score": rule_score
        }

    except Exception as e:
        logger.error(f"rule_check_failed - trace_id={trace_id}, error={str(e)}")

        # Return safe defaults on error
        return {
            "triggered_rules": [],
            "rule_score": 0.0,
            "errors": state.get("errors", []) + [f"Rule check failed: {str(e)}"]
        }


async def _evaluate_rule(payment: Dict[str, Any], rule: Any) -> Dict[str, Any] | None:
    """
    Evaluate a single rule against a payment transaction.

    Args:
        payment: Payment transaction data
        rule: ComplianceRule from rules_service

    Returns:
        Dict with violation details if rule is violated, None otherwise
    """
    rule_type = rule.rule_type

    # Transaction amount threshold checks
    if rule_type == "transaction_amount_threshold":
        threshold = rule.rule_data.get("threshold_value") or rule.rule_data.get("threshold_amount")
        if threshold is None:
            return None

        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            return None

        amount = float(payment.get("amount", 0))
        currency_filter = rule.rule_data.get("currency")
        payment_currency = str(payment.get("currency") or "").upper()

        if currency_filter:
            currency_filter_normalized = str(currency_filter).upper()
            if currency_filter_normalized and payment_currency != currency_filter_normalized:
                return None

        if amount > threshold_value:
            return {
                "details": (
                    f"Transaction amount {amount:.2f} {payment_currency or 'UNK'} "
                    f"exceeds threshold {threshold_value:.2f}"
                )
            }

    # Sanctions screening checks
    elif rule_type == "sanctions_screening":
        statuses = {
            status.lower()
            for status in rule.rule_data.get(
                "match_statuses",
                ["fail", "review", "potential_match", "hit"],
            )
        }
        screening_result = str(payment.get("sanctions_screening_result", "")).lower()
        if screening_result in statuses:
            return {
                "details": f"Sanctions screening flag: {payment.get('sanctions_screening_result')}"
            }

    # High-risk jurisdiction checks
    elif rule_type == "high_risk_jurisdiction":
        high_risk_countries = {
            country.upper()
            for country in rule.rule_data.get(
                "high_risk_countries",
                settings.high_risk_jurisdictions_list,
            )
        }

        originator_country = str(payment.get("originator_country") or "").upper()
        beneficiary_country = str(payment.get("beneficiary_country") or "").upper()

        match_direction = rule.rule_data.get("match_direction", "either")

        if match_direction == "originator":
            triggered = originator_country in high_risk_countries
        elif match_direction == "beneficiary":
            triggered = beneficiary_country in high_risk_countries
        else:
            triggered = (
                originator_country in high_risk_countries
                or beneficiary_country in high_risk_countries
            )

        if triggered:
            return {
                "details": (
                    "Transaction involves high-risk jurisdiction: "
                    f"{originator_country or '??'} -> {beneficiary_country or '??'}"
                )
            }

    # PEP (Politically Exposed Person) checks
    elif rule_type == "pep_screening":
        pep_statuses = {
            status.lower()
            for status in rule.rule_data.get(
                "match_statuses",
                ["confirmed", "fail", "review"],
            )
        }
        pep_status = str(
            payment.get("pep_screening_result")
            or payment.get("pep_status")
            or ""
        ).lower()

        if pep_status in pep_statuses:
            return {
                "details": f"PEP screening flag: {payment.get('pep_screening_result', pep_status.upper())}"
            }

    # Currency mismatch or unusual currency checks
    elif rule_type == "currency_restriction":
        restricted_currencies = {
            currency.upper()
            for currency in rule.rule_data.get("restricted_values", [])
        }
        currency = str(payment.get("currency") or "").upper()
        if currency and currency in restricted_currencies:
            return {
                "details": f"Restricted currency: {currency}"
            }

    # Missing required fields (data quality)
    elif rule_type == "missing_required_fields":
        required_fields = rule.rule_data.get(
            "required_fields",
            ["originator_name", "beneficiary_name", "originator_account", "beneficiary_account"],
        )
        missing = [
            field
            for field in required_fields
            if not payment.get(field)
        ]
        if missing:
            return {
                "details": f"Missing required fields: {', '.join(missing)}"
            }

    # No violation
    return None


def _severity_to_score(severity: str) -> float:
    """
    Convert rule severity to numeric score.

    Args:
        severity: Rule severity (critical/high/medium/low)

    Returns:
        Numeric score (0-40)
    """
    severity_map = {
        "critical": 40.0,
        "high": 30.0,
        "medium": 20.0,
        "low": 10.0
    }
    return severity_map.get(severity.lower(), 10.0)


def _calculate_rule_score(triggered_rules: List[Dict[str, Any]]) -> float:
    """
    Calculate aggregate rule score from triggered rules.

    Uses weighted average with decay to avoid score explosion.

    Args:
        triggered_rules: List of triggered rule violations

    Returns:
        Aggregate score (0-100)
    """
    if not triggered_rules:
        return 0.0

    # Sort by severity score (highest first)
    sorted_rules = sorted(
        triggered_rules,
        key=lambda r: r["severity_score"],
        reverse=True
    )

    # Weighted sum with exponential decay
    total_score = 0.0
    for idx, rule in enumerate(sorted_rules):
        weight = 0.5 ** idx  # Each subsequent rule has half the weight
        total_score += rule["severity_score"] * weight

    # Cap at 100
    return min(total_score, 100.0)
