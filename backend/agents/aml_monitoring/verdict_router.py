"""
Verdict Router - LangGraph node for determining final verdict and team assignment.
Implements deterministic verdict calculation based on risk scores.
"""
from typing import Dict, Any

from backend.core.observability import get_logger
from backend.agents.aml_monitoring.state_schemas import PaymentAnalysisState

logger = get_logger(__name__)


async def calculate_verdict_node(state: PaymentAnalysisState) -> Dict[str, Any]:
    """
    LangGraph node: Calculate final verdict and team assignment.

    Uses deterministic logic based on risk thresholds:
    - pass: risk_score < 30
    - suspicious: 30 <= risk_score < 70
    - fail: risk_score >= 70

    Team assignment logic:
    - legal: Sanctions or regulatory violations
    - compliance: Pattern-based risk (structuring, velocity, layering)
    - front_office: Data quality issues

    Args:
        state: Current PaymentAnalysisState from LangGraph workflow

    Returns:
        Dict with verdict, assigned_team, and justification
    """
    rule_score = state["rule_score"]
    pattern_score = state["pattern_score"]
    triggered_rules = state["triggered_rules"]
    detected_patterns = state["detected_patterns"]
    llm_risk_score = state.get("llm_risk_score", 0.0)
    llm_summary = state.get("llm_summary", "")
    llm_flagged_transactions = state.get("llm_flagged_transactions", [])
    llm_patterns = state.get("llm_patterns", [])
    trace_id = state["trace_id"]

    logger.info(
        "verdict_calculation_started - trace_id=%s, rule_score=%.2f, pattern_score=%.2f, llm_risk_score=%.2f",
        trace_id,
        rule_score,
        pattern_score,
        llm_risk_score,
    )

    # Calculate weighted risk score (LLM 50%, rules 30%, patterns 20%)
    risk_score = min(
        (rule_score * 0.3) + (pattern_score * 0.2) + (llm_risk_score * 0.5),
        100.0,
    )

    # Determine verdict based on risk score thresholds
    if risk_score >= 70:
        verdict = "fail"
    elif risk_score >= 30:
        verdict = "suspicious"
    else:
        verdict = "pass"

    # Determine team assignment based on violation types
    assigned_team = _determine_team_assignment(
        triggered_rules,
        detected_patterns,
        llm_patterns,
        llm_flagged_transactions,
    )

    # Generate justification
    justification = _generate_justification(
        verdict=verdict,
        risk_score=risk_score,
        rule_score=rule_score,
        pattern_score=pattern_score,
        llm_risk_score=llm_risk_score,
        triggered_rules=triggered_rules,
        detected_patterns=detected_patterns,
        llm_patterns=llm_patterns,
        llm_flagged=llm_flagged_transactions,
        llm_summary=llm_summary,
        assigned_team=assigned_team
    )

    logger.info(
        "verdict_calculated - trace_id=%s, verdict=%s, assigned_team=%s, risk_score=%.2f",
        trace_id,
        verdict,
        assigned_team,
        risk_score,
    )

    return {
        "verdict": verdict,
        "assigned_team": assigned_team,
        "risk_score": risk_score,
        "justification": justification
    }


def _determine_team_assignment(
    triggered_rules: list[Dict[str, Any]],
    detected_patterns: list[Dict[str, Any]],
    llm_patterns: list[Dict[str, Any]],
    llm_flagged: list[Dict[str, Any]],
) -> str:
    """
    Determine which team should handle this case.

    Priority order:
    1. Legal: Sanctions, regulatory violations, PEP involvement
    2. Compliance: Structuring, velocity anomalies, layering patterns
    3. Front Office: Data quality, missing fields

    Args:
        triggered_rules: List of violated compliance rules
        detected_patterns: List of detected AML patterns

    Returns:
        Team assignment (legal/compliance/front_office)
    """
    # Check for legal team triggers (highest priority)
    legal_rule_types = {
        "sanctions_screening",
        "pep_screening",
        "high_risk_jurisdiction",
        "regulatory_violation"
    }

    for rule in triggered_rules:
        if rule.get("rule_type") in legal_rule_types:
            return "legal"

    # Check for compliance team triggers
    compliance_pattern_types = {
        "structuring",
        "velocity_anomaly",
        "layering",
        "round_tripping",
        "smurfing"
    }

    for pattern in detected_patterns + llm_patterns:
        if pattern.get("pattern_type") in compliance_pattern_types:
            return "compliance"

    # Check for data quality issues (front office)
    data_quality_rule_types = {
        "missing_required_fields",
        "invalid_format",
        "data_inconsistency"
    }

    for rule in triggered_rules:
        if rule.get("rule_type") in data_quality_rule_types:
            return "front_office"

    for flagged in llm_flagged:
        reason = (flagged.get("reason") or "").lower()
        if any(keyword in reason for keyword in ["sanction", "pep", "regulatory"]):
            return "legal"
        if any(keyword in reason for keyword in ["pattern", "structuring", "velocity", "layering"]):
            return "compliance"
        if any(keyword in reason for keyword in ["missing", "incomplete", "documentation"]):
            return "front_office"

    # Default: compliance team handles all other cases
    return "compliance"


def _generate_justification(
    verdict: str,
    risk_score: float,
    rule_score: float,
    pattern_score: float,
    llm_risk_score: float,
    triggered_rules: list[Dict[str, Any]],
    detected_patterns: list[Dict[str, Any]],
    llm_patterns: list[Dict[str, Any]],
    llm_flagged: list[Dict[str, Any]],
    llm_summary: str,
    assigned_team: str
) -> str:
    """
    Generate human-readable justification for the verdict.

    Args:
        verdict: Final verdict (pass/suspicious/fail)
        risk_score: Overall risk score
        rule_score: Rule-based score
        pattern_score: Pattern-based score
        llm_risk_score: Weighted LLM-derived risk score (0-100)
        triggered_rules: List of violated rules
        detected_patterns: List of detected patterns
        assigned_team: Assigned team

    Returns:
        Justification string
    """
    parts = []

    # Verdict summary
    verdict_descriptions = {
        "pass": "Transaction cleared for processing",
        "suspicious": "Transaction flagged for review",
        "fail": "Transaction blocked pending investigation"
    }
    parts.append(f"{verdict_descriptions[verdict]} (Risk Score: {risk_score:.1f}/100)")

    # Rule violations
    if triggered_rules:
        rule_count = len(triggered_rules)
        parts.append(f"\n\nRule Violations ({rule_count}):")
        for rule in triggered_rules[:3]:  # Show top 3
            parts.append(f"- {rule['description']}: {rule['violation_details']}")
        if rule_count > 3:
            parts.append(f"- ... and {rule_count - 3} more")

    # Detected patterns
    if detected_patterns:
        pattern_count = len(detected_patterns)
        parts.append(f"\n\nDetected Patterns ({pattern_count}):")
        for pattern in detected_patterns[:3]:  # Show top 3
            parts.append(f"- {pattern['pattern_type']}: {pattern.get('description', 'Pattern detected')}")
        if pattern_count > 3:
            parts.append(f"- ... and {pattern_count - 3} more")

    # LLM identified patterns
    if llm_patterns:
        parts.append(f"\n\nLLM Identified Patterns ({len(llm_patterns)}):")
        for pattern in llm_patterns[:3]:
            parts.append(
                f"- {pattern.get('pattern_type', 'pattern')}: {pattern.get('description', 'Pattern detected')}"
            )

    if llm_flagged:
        parts.append(f"\n\nLLM Flagged Transactions ({len(llm_flagged)}):")
        for flagged in llm_flagged[:3]:
            parts.append(
                f"- {flagged.get('transaction_id', 'unknown')}: {flagged.get('reason', 'Flagged by LLM')}"
            )

    if llm_summary:
        parts.append("\n\nLLM Assessment Summary:\n")
        parts.append(llm_summary)

    # Scoring breakdown
    parts.append("\n\nScoring Breakdown:")
    parts.append(f"- Rule Score: {rule_score:.1f}/100 (30% weight)")
    parts.append(f"- Pattern Score: {pattern_score:.1f}/100 (20% weight)")
    parts.append(f"- LLM Risk Score: {llm_risk_score:.1f}/100 (50% weight)")

    # Team assignment rationale
    team_rationales = {
        "legal": "Assigned to Legal team due to sanctions, PEP, or regulatory concerns",
        "compliance": "Assigned to Compliance team for AML pattern analysis",
        "front_office": "Assigned to Front Office for data quality review"
    }
    parts.append(f"\n\n{team_rationales[assigned_team]}")

    return "".join(parts)
