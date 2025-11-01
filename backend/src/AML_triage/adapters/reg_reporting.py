"""Stub regulatory reporting adapter for STR drafts."""

from __future__ import annotations

from typing import Any, Dict


def create_str_draft(*, idempotency_key: str, jurisdiction: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "drafted",
        "jurisdiction": jurisdiction,
        "idempotency_key": idempotency_key,
        "payload": payload,
    }


__all__ = ["create_str_draft"]
