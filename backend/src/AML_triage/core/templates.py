"""Template registry management for AML triage prompts and communications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import yaml

from .config import Settings, load_settings


class TemplateIndexError(RuntimeError):
    """Raised when template metadata cannot be loaded."""


@dataclass
class TemplateSummary:
    template_id: str
    action_id: str
    version: str
    locale: str
    channel: str
    purpose: str
    when_to_use: str
    compliance_notes: str | None
    rules: List[str]
    risk_levels: List[str]
    corridors: List[str]


class TemplateRegistry:
    """Provides lookup and retrieval helpers for action templates."""

    def __init__(self, summaries: List[TemplateSummary]):
        self._by_action: Dict[str, List[TemplateSummary]] = {}
        for summary in summaries:
            self._by_action.setdefault(summary.action_id, []).append(summary)

    def summaries_for_action(self, action_id: str) -> List[TemplateSummary]:
        return self._by_action.get(action_id, [])

    def filter_for_context(
        self,
        action_id: str,
        *,
        rule_codes: Iterable[str],
        corridor: str,
        k: int,
    ) -> List[TemplateSummary]:
        candidates = self.summaries_for_action(action_id)
        if not candidates:
            return []
        codes = set(rule_codes)
        filtered = [
            summary
            for summary in candidates
            if (not summary.rules or codes.intersection(summary.rules))
            and (not summary.corridors or corridor in summary.corridors)
        ]
        if not filtered:
            filtered = candidates
        return filtered[:k]

    def actions(self) -> Iterable[str]:
        return self._by_action.keys()


def _load_index(path: Path) -> Dict[str, Sequence[str]]:
    if not path.exists():
        raise TemplateIndexError(f"template index missing at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_template_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_template_registry(settings: Settings | None = None) -> TemplateRegistry:
    settings = settings or load_settings()
    index_path = settings.templates_dir / "index.json"
    mapping = _load_index(index_path)

    summaries: List[TemplateSummary] = []
    errors: List[str] = []

    for action_id, template_ids in mapping.items():
        for template_id in template_ids:
            template_path = settings.templates_dir / "action_templates" / f"{template_id}.yaml"
            if not template_path.exists():
                errors.append(f"template {template_id} missing for action {action_id}")
                continue
            raw = _load_template_file(template_path)
            try:
                summary = TemplateSummary(
                    template_id=template_id,
                    action_id=action_id,
                    version=str(raw.get("version", "1.0.0")),
                    locale=str(raw.get("locale", "en")),
                    channel=str(raw.get("channel", "EMAIL")),
                    purpose=str(raw.get("purpose", "")),
                    when_to_use=str(raw.get("when_to_use", "")),
                    compliance_notes=raw.get("compliance_notes"),
                    rules=list(raw.get("rules", [])),
                    risk_levels=list(raw.get("risk_levels", [])),
                    corridors=list(raw.get("corridors", [])),
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                errors.append(f"template {template_id} invalid: {exc}")
                continue
            summaries.append(summary)

    if errors:
        raise TemplateIndexError("; ".join(errors))

    return TemplateRegistry(sorted(summaries, key=lambda item: item.version, reverse=True))


__all__ = ["TemplateRegistry", "TemplateSummary", "load_template_registry", "TemplateIndexError"]
