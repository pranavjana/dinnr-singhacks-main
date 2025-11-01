"""Generate reviewer-facing analysis reports from free-form case summaries."""

from __future__ import annotations

import textwrap
from typing import Iterable, List

from .config import Settings, load_settings
from .groq_client import GroqClient
from .playbooks import ActionPlaybook, ActionPlaybookRegistry, PlaybookNotFoundError
from .validation import SchemaValidationError, hash_payload


class ReportGenerationError(RuntimeError):
    """Raised when a reviewer report cannot be produced."""


class ReportGenerator:
    """Coordinate playbook lookup and LLM prompting for reviewer reports."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        playbooks: ActionPlaybookRegistry | None = None,
        groq_client: GroqClient | None = None,
    ):
        self.settings = settings or load_settings()
        self.playbooks = playbooks or ActionPlaybookRegistry(self.settings)
        self.groq_client = groq_client or GroqClient(self.settings)

    async def generate_report(self, case_summary: str) -> str:
        summary = (case_summary or "").strip()
        if not summary:
            raise SchemaValidationError(
                "Case summary missing",
                errors=[{"path": [], "message": "Provide a short text describing the alert context.", "validator": "minLength"}],
            )

        prompt = self._build_prompt(summary)
        cache_key = hash_payload({"summary": summary})

        try:
            return await self.groq_client.generate_reviewer_report(prompt=prompt, cache_key=cache_key)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise ReportGenerationError(str(exc)) from exc

    def _playbook_digest(self) -> str:
        sections: List[str] = []
        try:
            action_ids = sorted(self.playbooks.actions())
        except PlaybookNotFoundError as exc:
            raise ReportGenerationError(str(exc)) from exc

        for action_id in action_ids:
            playbook = self.playbooks.get(action_id)
            sections.append(self._format_playbook(playbook))
        return "\n\n".join(sections)

    @staticmethod
    def _format_playbook(playbook: ActionPlaybook) -> str:
        lines = [
            f"Action ID: {playbook.action_id}",
            f"Title: {playbook.title}",
            f"Objective: {playbook.objective}",
            "Key next steps:",
        ]
        lines.extend(f"  - {step}" for step in playbook.next_steps)
        if playbook.reviewer_checks:
            lines.append("Reviewer checks:")
            lines.extend(f"  - {check}" for check in playbook.reviewer_checks)
        lines.append(f"Approvals: {playbook.approvals}")
        return "\n".join(lines)

    def _build_prompt(self, case_summary: str) -> str:
        instructions = textwrap.dedent(
            """
            You are an AML Level 2 reviewer assistant. Given the investigator's short case summary,
            produce a polished report for the human reviewer. Requirements:
            - Begin with an executive summary explaining the key risks and why the customer/transaction is flagged.
            - Recommend concrete follow-up actions, choosing from the approved playbooks provided.
            - For each recommended action, explain why it is relevant, reference important playbook steps, and note any approvals.
            - Suggest monitoring items or contingencies (e.g., what to do if documentation is missing, when to escalate).
            - Use professional, concise language. Output plain text formatted with paragraphs and bullet lists.
            - Do not invent actions that are not present in the playbook list.
            """
        ).strip()

        playbook_digest = self._playbook_digest()

        sections = [
            instructions,
            "=== Case Summary ===",
            case_summary,
            "=== Approved Action Playbooks ===",
            playbook_digest,
        ]

        return "\n".join(sections)


__all__ = ["ReportGenerator", "ReportGenerationError"]
