"""Stub account control adapter for soft holds."""

from __future__ import annotations

from typing import Any, Dict


def place_soft_hold(*, idempotency_key: str, account_id: str | None, reason: str) -> Dict[str, Any]:
    return {
        "status": "pending",
        "hold_reference": f"HOLD-{idempotency_key[:8]}",
        "reason": reason,
        "account_hash": account_id,
    }


__all__ = ["place_soft_hold"]
