"""Stub routing adapter for assigning work queues."""

from __future__ import annotations

from typing import Any, Dict


def assign_team(*, idempotency_key: str, team: str, context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "queued",
        "team": team,
        "idempotency_key": idempotency_key,
        "context": context,
    }


__all__ = ["assign_team"]
