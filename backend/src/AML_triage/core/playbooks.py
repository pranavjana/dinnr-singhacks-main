"""Action playbook lookup utilities for reviewer guidance."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List

import yaml

from .config import Settings, load_settings


class PlaybookNotFoundError(RuntimeError):
    """Raised when an action playbook entry cannot be located."""


@dataclass(frozen=True)
class ActionPlaybook:
    action_id: str
    title: str
    objective: str
    next_steps: List[str]
    reviewer_checks: List[str]
    approvals: str


@lru_cache(maxsize=1)
def _load_playbooks(path: Path) -> Dict[str, ActionPlaybook]:
    if not path.exists():
        raise PlaybookNotFoundError(f"action playbooks missing at {path}")

    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    playbooks: Dict[str, ActionPlaybook] = {}
    for action_id, data in raw.items():
        playbooks[action_id] = ActionPlaybook(
            action_id=action_id,
            title=str(data.get("title", action_id)),
            objective=str(data.get("objective", "")),
            next_steps=list(data.get("next_steps", [])),
            reviewer_checks=list(data.get("reviewer_checks", [])),
            approvals=str(data.get("approvals", "")),
        )
    return playbooks


class ActionPlaybookRegistry:
    """Provide read access to action playbook descriptions."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self._path = self.settings.templates_dir / "action_playbooks.yaml"

    def get(self, action_id: str) -> ActionPlaybook:
        playbooks = _load_playbooks(self._path)
        if action_id not in playbooks:
            raise PlaybookNotFoundError(f"no playbook available for {action_id}")
        return playbooks[action_id]

    def actions(self) -> Iterable[str]:
        return _load_playbooks(self._path).keys()


__all__ = ["ActionPlaybook", "ActionPlaybookRegistry", "PlaybookNotFoundError"]
