"""Action catalogue loading and guardrail helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, Field, ValidationError

from .config import Settings, load_settings


class ActionRule(BaseModel):
    decision: List[str] | None = None
    rule_codes: List[str] | None = None
    high_risk_corridor: bool | None = None


class ActionEntry(BaseModel):
    action_id: str
    description: str
    requires_approval: bool
    allowed_if: List[ActionRule] = Field(default_factory=list)
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)
    compliance_notes: str | None = None
    risk_tier: str | None = None


class ActionCatalogueError(RuntimeError):
    """Raised when action catalogue cannot be loaded."""


@dataclass
class ActionCatalogue:
    entries: Dict[str, ActionEntry]

    def get(self, action_id: str) -> ActionEntry:
        if action_id not in self.entries:
            raise KeyError(f"action {action_id} is not whitelisted")
        return self.entries[action_id]

    @property
    def allowed_actions(self) -> Iterable[str]:
        return self.entries.keys()


def _load_catalogue_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise ActionCatalogueError(f"Action catalogue missing at {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_action_catalogue(settings: Settings | None = None) -> ActionCatalogue:
    """Load and validate action catalogue entries."""

    settings = settings or load_settings()
    path = settings.templates_dir / "action_catalogue.json"
    raw_entries = _load_catalogue_file(path)

    entries: Dict[str, ActionEntry] = {}
    errors: List[str] = []

    for idx, raw in enumerate(raw_entries):
        try:
            entry = ActionEntry.model_validate(raw)
        except ValidationError as exc:
            errors.append(f"entry[{idx}] invalid: {exc}")
            continue

        if entry.action_id in entries:
            errors.append(f"duplicate action_id {entry.action_id}")
            continue

        entries[entry.action_id] = entry

    if errors:
        raise ActionCatalogueError("; ".join(errors))

    return ActionCatalogue(entries)


__all__ = ["ActionCatalogue", "load_action_catalogue", "ActionCatalogueError"]
