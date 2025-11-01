"""Deterministic plan builder coordinating validation, catalogue, and templates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from .actions import ActionCatalogue, ActionRule, load_action_catalogue
from .config import Settings, load_settings
from .groq_client import GroqClient
from .storage import Storage
from .templates import TemplateRegistry, TemplateSummary, load_template_registry
from .validation import SchemaValidationError, hash_payload, validate_screening_result

FATF_HIGH_RISK_COUNTRIES = {
    "IRN",
    "PRK",
    "MMR",
    "SYR",
    "RUS",
    "ZWE",
}


class PlanBuilder:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        catalogue: ActionCatalogue | None = None,
        templates: TemplateRegistry | None = None,
        storage: Storage | None = None,
        groq_client: GroqClient | None = None,
    ):
        self.settings = settings or load_settings()
        self.catalogue = catalogue or load_action_catalogue()
        self.templates = templates or load_template_registry()
        self.storage = storage or Storage(self.settings)
        self.groq_client = groq_client or GroqClient(self.settings)

    async def build_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalised, schema_version, aliases_used = validate_screening_result(payload)
        input_hash = hash_payload(normalised)

        existing = self.storage.plan_exists(input_hash)
        if existing:
            return existing

        corridor_risk, is_high_risk_corridor = self._determine_corridor_risk(normalised)
        amount = normalised.get("amount", 0)
        escalation_required = is_high_risk_corridor and amount >= 10000

        matched_actions = self._select_actions(normalised, escalation_required)
        communications, templates_used = self._build_communications(normalised, matched_actions, corridor_risk)

        suggestion = await self.groq_client.generate_plan_suggestion(
            prompt=self._build_prompt(normalised, matched_actions, corridor_risk),
            schema={
                "type": "object",
                "required": ["rationale", "confidence"],
                "properties": {
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
            cache_key=input_hash,
        )

        plan_id = str(uuid.uuid4())
        approvals_required = self._build_approvals(matched_actions)
        approvals_pending = sum(1 for approval in approvals_required if approval["status"] == "PENDING")

        rationales = [action["rationale"] for action in matched_actions]
        rationales.append(suggestion.rationale)
        confidence_values = [action["confidence"] for action in matched_actions] or [0.5]
        confidence_values.append(suggestion.confidence)
        confidence_avg = round(sum(confidence_values) / len(confidence_values), 3)

        plan_payload = {
            "plan_id": plan_id,
            "input_hash": input_hash,
            "schema_version": schema_version,
            "summary": {
                "action_counts": self._count_actions(matched_actions),
                "approvals_pending": approvals_pending,
                "corridor_risk": corridor_risk,
                "confidence_avg": confidence_avg,
            },
            "recommended_actions": [self._render_action(action) for action in matched_actions],
            "communications": communications,
            "rationales": rationales,
            "confidence": confidence_avg,
            "approvals_required": approvals_required,
            "audit": {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": schema_version,
                "aliases_used": aliases_used,
                "templates_used": templates_used,
                "plan_hash": hash_payload({"actions": [a["action_id"] for a in matched_actions]}),
                "agent_iterations": 1,
                "offline_mode": self.settings.offline_mode,
            },
        }

        provided_action_ids = normalised.get("action_ids")
        if provided_action_ids:
            plan_payload["summary"]["source_action_ids"] = list(provided_action_ids)
        if normalised.get("analysis_report"):
            plan_payload["analysis_report"] = normalised["analysis_report"]

        self.storage.save_plan(plan_payload)
        return plan_payload

    def _determine_corridor_risk(self, payload: Dict[str, Any]) -> Tuple[str, bool]:
        corridor = payload.get("corridor", {})
        origin = corridor.get("origin_country", "")
        destination = corridor.get("destination_country", "")
        if origin in FATF_HIGH_RISK_COUNTRIES or destination in FATF_HIGH_RISK_COUNTRIES:
            return "HIGH", True
        return "MEDIUM", False

    def _select_actions(self, payload: Dict[str, Any], escalation_required: bool) -> List[Dict[str, Any]]:
        provided_action_ids = payload.get("action_ids") or []
        rule_codes = set(payload.get("rule_codes", []))
        behavioural_patterns = payload.get("behavioural_patterns", [])

        if provided_action_ids:
            return self._actions_from_ids(provided_action_ids, rule_codes, behavioural_patterns)

        decision = payload.get("decision")

        actions: List[Dict[str, Any]] = []
        for action_entry in self.catalogue.entries.values():
            if not self._matches_any_rule(action_entry.allowed_if, decision, rule_codes, escalation_required):
                continue
            confidence = 0.85 if action_entry.risk_tier == "HIGH" else 0.75
            rationale = self._derive_rationale(action_entry.action_id, rule_codes, behavioural_patterns)
            actions.append(
                {
                    "action_id": action_entry.action_id,
                    "entry": action_entry,
                    "confidence": confidence,
                    "rationale": rationale,
                }
            )

        if not actions and decision == "PASS":
            actions.append(
                {
                    "action_id": "NO_ACTION",
                    "entry": None,
                    "confidence": 0.9,
                    "rationale": "PASS decision with no residual risk; closing alert.",
                }
            )

        return actions

    def _actions_from_ids(
        self,
        action_ids: Iterable[str],
        rule_codes: Iterable[str],
        patterns: Iterable[str],
    ) -> List[Dict[str, Any]]:
        deduped: List[str] = []
        seen: set[str] = set()
        for action_id in action_ids:
            if action_id not in seen:
                seen.add(action_id)
                deduped.append(action_id)

        actions: List[Dict[str, Any]] = []
        for action_id in deduped:
            try:
                entry = self.catalogue.get(action_id)
            except KeyError as exc:
                raise SchemaValidationError(
                    f"Action {action_id} is not recognised",
                    errors=[
                        {
                            "path": ["action_ids"],
                            "message": f"action_id '{action_id}' not found in catalogue",
                            "validator": "catalogue",
                        }
                    ],
                ) from exc

            confidence = 0.85 if entry.risk_tier == "HIGH" else 0.75
            rationale = self._derive_rationale(entry.action_id, rule_codes, patterns)
            actions.append(
                {
                    "action_id": entry.action_id,
                    "entry": entry,
                    "confidence": confidence,
                    "rationale": rationale,
                }
            )

        return actions

    def _matches_any_rule(self, rules: Iterable[ActionRule], decision: str, rule_codes: set[str], escalation_required: bool) -> bool:
        for rule in rules:
            decision_match = not rule.decision or decision in rule.decision
            rule_code_match = not rule.rule_codes or bool(rule_codes.intersection(rule.rule_codes))
            high_risk_match = rule.high_risk_corridor is None or rule.high_risk_corridor == escalation_required
            if decision_match and rule_code_match and high_risk_match:
                return True
        return False

    def _derive_rationale(self, action_id: str, rule_codes: Iterable[str], patterns: Iterable[str]) -> str:
        if action_id == "NO_ACTION":
            return "No follow-up actions required; documented closure."
        rule_list = ", ".join(rule_codes) if rule_codes else "baseline policy"
        pattern_list = ", ".join(patterns) if patterns else "no behavioural anomalies"
        return f"Action {action_id} recommended due to rules [{rule_list}] and patterns [{pattern_list}]."

    def _build_communications(
        self,
        payload: Dict[str, Any],
        actions: List[Dict[str, Any]],
        corridor_risk: str,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        rule_codes = payload.get("rule_codes", [])
        corridor = payload.get("corridor", {})
        corridor_key = corridor.get("origin_country", "") + "-" + corridor.get("destination_country", "")

        communications: List[Dict[str, Any]] = []
        templates_used: set[str] = set()
        for action in actions:
            entry = action.get("entry")
            if not entry or not entry.tool.startswith("comms."):
                continue
            summaries = self.templates.filter_for_context(
                entry.action_id,
                rule_codes=rule_codes,
                corridor=corridor_risk,
                k=self.settings.template_top_k,
            )
            for summary in summaries:
                communications.append(
                    {
                        "template_id": summary.template_id,
                        "audience": "RM" if entry.params.get("audience") == "RM" else "CUSTOMER",
                        "tone": "PROFESSIONAL_INTERNAL" if entry.params.get("audience") == "RM" else "NEUTRAL_EXTERNAL",
                        "placeholders": {
                            "customer_reference": payload.get("metadata", {}).get("customer_id_hash", "hash:unknown"),
                            "corridor": corridor_key,
                            "rule_codes": ",".join(rule_codes),
                        },
                        "delivery_channel": "EMAIL" if summary.channel == "EMAIL" else "PORTAL_TASK",
                    }
                )
                templates_used.add(summary.template_id)

        return communications, sorted(templates_used)

    def _build_prompt(
        self,
        payload: Dict[str, Any],
        actions: List[Dict[str, Any]],
        corridor_risk: str,
    ) -> str:
        rule_codes = ", ".join(payload.get("rule_codes", [])) or "none"
        decision = payload.get("decision")
        summary = ", ".join(action["action_id"] for action in actions) or "NO_ACTION"
        analysis_report = payload.get("analysis_report")
        return (
            "You are an AML policy assistant. Provide a concise rationale summarising why the "
            f"decision {decision} with rules [{rule_codes}] and corridor risk {corridor_risk} leads to "
            f"actions [{summary}]."
            + (f" Prior investigation summary: {analysis_report}" if analysis_report else "")
        )

    def _build_approvals(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        approvals: List[Dict[str, Any]] = []
        for action in actions:
            entry = action.get("entry")
            if entry and entry.requires_approval:
                approver_role = "MLRO" if entry.action_id == "FILE_STR_DRAFT" else "COMPLIANCE_REVIEWER"
                approvals.append(
                    {
                        "action_id": entry.action_id,
                        "approver_role": approver_role,
                        "status": "PENDING",
                    }
                )
        return approvals

    def _count_actions(self, actions: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for action in actions:
            action_id = action["action_id"]
            counts[action_id] = counts.get(action_id, 0) + 1
        return counts

    def _render_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        entry = action.get("entry")
        requires_approval = bool(entry.requires_approval) if entry else False
        template_ids = []
        if entry and entry.tool.startswith("comms."):
            template_ids = [summary.template_id for summary in self.templates.summaries_for_action(entry.action_id)]

        return {
            "action_id": action["action_id"],
            "status": "SUGGESTED",
            "priority": 1,
            "rationale": action["rationale"],
            "confidence": action["confidence"],
            "requires_approval": requires_approval,
            "template_ids": template_ids,
        }


__all__ = ["PlanBuilder", "SchemaValidationError"]
