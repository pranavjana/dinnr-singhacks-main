"""Stub case management adapter used for demo purposes."""

from __future__ import annotations

from typing import Any, Dict


def create_case(*, idempotency_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "success",
        "idempotency_key": idempotency_key,
        "case_reference": f"CASE-{idempotency_key[:8]}",
        "payload": payload,
    }


__all__ = ["create_case"]
