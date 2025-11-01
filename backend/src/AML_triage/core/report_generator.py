"""Generate reviewer-facing analysis reports from LLM3 recommendations."""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from pydantic import ValidationError

from .actions import ActionCatalogue, load_action_catalogue
from .config import Settings, load_settings
from .groq_client import GroqClient
from .playbooks import ActionPlaybookRegistry, PlaybookNotFoundError
from .report_models import LLM3Payload
from .validation import SchemaValidationError, hash_payload


class ReportGenerationError(RuntimeError):
    """Raised when a reviewer report cannot be produced."""


@dataclass
class ResolvedActionContext:
    action_id: str
    title: str
    objective: str
    next_steps: List[str]
    reviewer_checks: List[str]
    approvals: str
    upstream_confidence: float | None
    why_not_primary: str | None = None
    template_id: str | None = None


class ReportGenerator:
    """Coordinate playbook lookup and LLM prompting for reviewer reports."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        catalogue: ActionCatalogue | None = None,
        playbooks: ActionPlaybookRegistry | None = None,
        groq_client: GroqClient | None = None,
    ):
        self.settings = settings or load_settings()
        self.catalogue = catalogue or load_action_catalogue()
        self.playbooks = playbooks or ActionPlaybookRegistry(self.settings)
        self.groq_client = groq_client or GroqClient(self.settings)

    async def generate_report(self, payload: Dict[str, Any]) -> str:
        try:
            model = LLM3Payload.model_validate(payload)
        except ValidationError as exc:
            raise SchemaValidationError("Invalid LLM3 payload", errors=exc.errors()) from exc

        action_context = self._build_action_context(model)
        prompt = self._build_prompt(model, action_context)
        cache_key = hash_payload({"trace_id": model.trace_id, "recommended": [ctx.action_id for ctx in action_context]})

        try:
            return await self.groq_client.generate_reviewer_report(prompt=prompt, cache_key=cache_key)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ReportGenerationError(str(exc)) from exc

    def _build_action_context(self, payload: LLM3Payload) -> List[ResolvedActionContext]:
        ids = payload.recommended_actions()
        if not ids:
            raise SchemaValidationError(
                "No recommended actions supplied",
                errors=[
                    {"path": ["ranked_actions"], "message": "At least one action_id is required.", "validator": "minItems"}
                ],
            )

        contexts: List[ResolvedActionContext] = []
        upstream_confidence_map = self._confidence_lookup(payload)
        why_not_map = {alt.action_id: alt.why_not_primary for alt in payload.alternatives}
        template_lookup = self._template_lookup(payload)

        for action_id in ids:
            try:
                _ = self.catalogue.get(action_id)
            except KeyError as exc:
                raise SchemaValidationError(
                    f"Action {action_id} not recognised",
                    errors=[
                        {
                            "path": ["ranked_actions"],
                            "message": f"action_id '{action_id}' not found in catalogue",
                            "validator": "catalogue",
                        }
                    ],
                ) from exc

            try:
                playbook = self.playbooks.get(action_id)
            except PlaybookNotFoundError as exc:
                raise ReportGenerationError(str(exc)) from exc

            contexts.append(
                ResolvedActionContext(
                    action_id=action_id,
                    title=playbook.title,
                    objective=playbook.objective,
                    next_steps=playbook.next_steps,
                    reviewer_checks=playbook.reviewer_checks,
                    approvals=playbook.approvals,
                    upstream_confidence=upstream_confidence_map.get(action_id),
                    why_not_primary=why_not_map.get(action_id),
                    template_id=template_lookup.get(action_id),
                )
            )

        return contexts

    @staticmethod
    def _confidence_lookup(payload: LLM3Payload) -> Dict[str, float | None]:
        lookup: Dict[str, float | None] = {}
        if payload.primary_action:
            lookup[payload.primary_action.action_id] = payload.primary_action.confidence
        for alt in payload.alternatives:
            lookup[alt.action_id] = alt.confidence
        for ranked in payload.ranked_actions:
            if ranked.action_id not in lookup:
                lookup[ranked.action_id] = ranked.confidence
        return lookup

    @staticmethod
    def _template_lookup(payload: LLM3Payload) -> Dict[str, str | None]:
        mapping: Dict[str, str | None] = {}
        if payload.primary_action and payload.primary_action.template_id:
            mapping[payload.primary_action.action_id] = payload.primary_action.template_id
        for alt in payload.alternatives:
            if alt.template_id:
                mapping[alt.action_id] = alt.template_id
        for ranked in payload.ranked_actions:
            # ranked schema may not provide template_id
            mapping.setdefault(ranked.action_id, None)
        return mapping

    def _build_prompt(self, payload: LLM3Payload, actions: Iterable[ResolvedActionContext]) -> str:
        signals = payload.resolved_signals()
        signal_lines = []
        for signal in signals:
            parts = [signal.rule_id]
            if signal.title:
                parts.append(signal.title)
            if signal.explanation:
                parts.append(signal.explanation)
            signal_lines.append(" - ".join(parts))

        action_sections: List[str] = []
        for ctx in actions:
            section = [
                f"Action ID: {ctx.action_id}",
                f"Title: {ctx.title}",
                f"Objective: {ctx.objective}",
            ]
            if ctx.template_id:
                section.append(f"Template ID: {ctx.template_id}")
            if ctx.upstream_confidence is not None:
                section.append(f"Confidence: {ctx.upstream_confidence:.2f}")
            section.append("Next steps:")
            section.extend(f"  - {step}" for step in ctx.next_steps)
            if ctx.reviewer_checks:
                section.append("Reviewer checks:")
                section.extend(f"  - {check}" for check in ctx.reviewer_checks)
            section.append(f"Approvals: {ctx.approvals}")
            if ctx.why_not_primary:
                section.append(f"Why not primary: {ctx.why_not_primary}")
            action_sections.append("\n".join(section))

        notes_block = "\n".join(f"- {note}" for note in payload.notes_for_llm4) or "None supplied."

        txn_block_lines: List[str] = []
        if payload.txn_snapshot:
            snap = payload.txn_snapshot
            txn_block_lines.append(f"Reference: {snap.transaction_ref or 'n/a'}")
            txn_block_lines.append(f"Booked at: {snap.booking_datetime or 'n/a'}")
            txn_block_lines.append(
                f"Amount: {snap.amount} {snap.currency} via {snap.channel} ({', '.join(snap.countries) or 'n/a'})"
            )
            if snap.behaviour_summary_30d:
                beh = snap.behaviour_summary_30d
                txn_block_lines.append(
                    f"30d behaviour: credits={beh.credits_count}, debits={beh.debits_count}, turnaround={beh.median_turnaround_hours}h, beneficiaries={beh.unique_beneficiaries}"
                )
        txn_block = "\n".join(txn_block_lines) or "Not provided."

        profile_lines = [f"{key}: {value}" for key, value in payload.profile_considerations.items()]
        profile_block = "\n".join(profile_lines) or "Not provided."

        instructions = textwrap.dedent(
            """
            You are an AML Level 2 reviewer helper. Write a concise, human-readable analysis report for the investigator.
            Requirements:
            - Start with a one-paragraph executive summary explaining why the case is flagged and the recommended action path.
            - Provide a bulleted breakdown of the recommended actions, referencing playbook steps and approvals.
            - Highlight any alternative actions and why they were deprioritised if applicable.
            - Call out risk signals and transaction context that justify the recommendation.
            - Close with clear next steps for the reviewer (what to monitor, follow-up timing, outstanding evidence).
            - Do not invent template IDs or actions beyond those provided.
            - Keep the tone professional and actionable.
            """
        ).strip()

        sections = [
            instructions,
            "=== Case Overview ===",
            f"Trace ID: {payload.trace_id}",
            f"Decision: {payload.decision}",
            f"Risk Level: {payload.risk_level or 'unspecified'}",
            "Signals:",
            "\n".join(f"- {line}" for line in signal_lines) or "- None supplied",
            "Profile considerations:",
            profile_block,
            "Transaction snapshot:",
            txn_block,
            "Notes from upstream:",
            notes_block,
            "=== Recommended Actions ===",
            "\n\n".join(action_sections),
        ]

        return "\n".join(sections)


__all__ = ["ReportGenerator", "ReportGenerationError"]
