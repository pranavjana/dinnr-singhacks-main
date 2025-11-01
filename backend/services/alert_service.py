"""
Alert Service - Alert generation and management for suspicious/failed payments.
Creates alerts for compliance, legal, and front office teams.
"""
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from backend.core.observability import get_logger
from backend.core.config import settings

logger = get_logger(__name__)


class AlertService:
    """
    Service for creating and managing payment alerts.

    Generates alerts for:
    - Suspicious transactions (flagged for review)
    - Failed transactions (blocked pending investigation)

    Alerts are assigned to teams and include investigation steps.
    """

    def __init__(self):
        self.logger = logger

    async def create_alert(
        self,
        payment_id: UUID,
        verdict_id: UUID,
        trace_id: UUID,
        verdict: str,
        assigned_team: str,
        risk_score: float,
        triggered_rules: List[Dict[str, Any]],
        detected_patterns: List[Dict[str, Any]],
        justification: str
    ) -> Optional[UUID]:
        """
        Create alert for suspicious or failed payment.

        Only creates alerts for 'suspicious' and 'fail' verdicts.
        Pass verdicts do not generate alerts.

        Args:
            payment_id: Payment transaction ID
            verdict_id: Verdict ID
            trace_id: Analysis trace ID
            verdict: Verdict type (pass/suspicious/fail)
            assigned_team: Team assignment (front_office/compliance/legal)
            risk_score: Overall risk score
            triggered_rules: List of violated rules
            detected_patterns: List of detected patterns
            justification: Verdict justification

        Returns:
            Alert ID if created, None for pass verdicts
        """
        # Don't create alerts for pass verdicts
        if verdict == "pass":
            self.logger.info(f"alert_skipped_for_pass - trace_id=str(trace_id)")
            return None

        # Determine alert priority based on verdict and risk score
        priority = self._calculate_alert_priority(verdict, risk_score)

        # Generate investigation steps
        investigation_steps = self._generate_investigation_steps(
            verdict=verdict,
            assigned_team=assigned_team,
            triggered_rules=triggered_rules,
            detected_patterns=detected_patterns
        )

        self.logger.info(f"creating_alert - trace_id=str(trace_id), payment_id=str(payment_id), priority=priority, assigned_team=assigned_team")

        # TODO: Insert into alerts table
        # INSERT INTO alerts (
        #     payment_id, verdict_id, trace_id, assigned_team,
        #     priority, status, investigation_steps, created_at
        # ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NOW())
        # RETURNING alert_id

        alert_id = uuid4()  # Placeholder

        self.logger.info(f"alert_created - trace_id=str(trace_id), alert_id=str(alert_id), priority=priority")

        return alert_id

    async def get_alert(self, alert_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert dict or None if not found
        """
        self.logger.info("fetching_alert", alert_id=str(alert_id))

        # TODO: Query alerts table
        # SELECT * FROM alerts WHERE alert_id = ?

        return None

    async def get_alerts_by_team(
        self,
        team: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get alerts assigned to a specific team.

        Args:
            team: Team name (front_office/compliance/legal)
            status: Optional status filter (pending/in_progress/resolved)
            limit: Maximum number of alerts to return

        Returns:
            List of alerts
        """
        self.logger.info(f"fetching_team_alerts - team=team, status=status, limit=limit")

        # TODO: Query alerts table
        # SELECT * FROM alerts
        # WHERE assigned_team = ?
        # AND (status = ? OR ? IS NULL)
        # ORDER BY priority DESC, created_at DESC
        # LIMIT ?

        return []

    async def update_alert_status(
        self,
        alert_id: UUID,
        status: str,
        investigation_notes: Optional[str] = None
    ) -> bool:
        """
        Update alert status and investigation notes.

        Args:
            alert_id: Alert ID
            status: New status (pending/in_progress/resolved/false_positive)
            investigation_notes: Optional investigation notes

        Returns:
            True if updated successfully
        """
        self.logger.info(f"updating_alert_status - alert_id=str(alert_id), status=status")

        # TODO: Update alerts table
        # UPDATE alerts
        # SET status = ?, investigation_notes = ?, updated_at = NOW()
        # WHERE alert_id = ?

        return True

    async def get_pending_alerts_count(self, team: Optional[str] = None) -> int:
        """
        Get count of pending alerts.

        Args:
            team: Optional team filter

        Returns:
            Count of pending alerts
        """
        # TODO: Query alerts table
        # SELECT COUNT(*) FROM alerts
        # WHERE status = 'pending'
        # AND (assigned_team = ? OR ? IS NULL)

        return 0

    def _calculate_alert_priority(self, verdict: str, risk_score: float) -> str:
        """
        Calculate alert priority based on verdict and risk score.

        Args:
            verdict: Verdict type (suspicious/fail)
            risk_score: Overall risk score (0-100)

        Returns:
            Priority level (critical/high/medium/low)
        """
        if verdict == "fail":
            # Failed transactions are always high or critical priority
            if risk_score >= 85:
                return "critical"
            else:
                return "high"
        elif verdict == "suspicious":
            # Suspicious transactions are medium or high priority
            if risk_score >= 50:
                return "high"
            else:
                return "medium"
        else:
            return "low"

    def _generate_investigation_steps(
        self,
        verdict: str,
        assigned_team: str,
        triggered_rules: List[Dict[str, Any]],
        detected_patterns: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate investigation steps based on violations.

        Args:
            verdict: Verdict type
            assigned_team: Assigned team
            triggered_rules: List of violated rules
            detected_patterns: List of detected patterns

        Returns:
            List of investigation steps
        """
        steps = []

        # Team-specific initial steps
        if assigned_team == "legal":
            steps.append("Review sanctions screening results")
            steps.append("Verify PEP status and relationships")
            steps.append("Check regulatory compliance requirements")
        elif assigned_team == "compliance":
            steps.append("Analyze transaction patterns and history")
            steps.append("Review AML risk indicators")
            steps.append("Assess customer due diligence documentation")
        elif assigned_team == "front_office":
            steps.append("Verify transaction data accuracy")
            steps.append("Contact originator for missing information")
            steps.append("Validate account details and beneficiary information")

        # Add rule-specific steps
        for rule in triggered_rules[:3]:  # Top 3 rules
            rule_type = rule.get("rule_type")
            if rule_type == "sanctions_screening":
                steps.append("Perform enhanced sanctions screening")
            elif rule_type == "transaction_amount_threshold":
                steps.append("Request source of funds documentation")
            elif rule_type == "high_risk_jurisdiction":
                steps.append("Review country risk assessment")

        # Add pattern-specific steps
        for pattern in detected_patterns[:3]:  # Top 3 patterns
            pattern_type = pattern.get("pattern_type")
            if pattern_type == "structuring":
                steps.append("Investigate potential structuring scheme")
            elif pattern_type == "velocity_anomaly":
                steps.append("Analyze transaction frequency and timing")
            elif pattern_type == "high_risk_jurisdiction":
                steps.append("Verify legitimate business purpose")

        # Final step
        if verdict == "fail":
            steps.append("Escalate to senior compliance officer if unresolved")
        else:
            steps.append("Document findings and decision rationale")

        return steps


# Global service instance
alert_service = AlertService()
