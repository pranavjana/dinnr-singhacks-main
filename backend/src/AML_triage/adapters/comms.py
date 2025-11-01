"""Stub communications adapter returning rendered template preview."""

from __future__ import annotations

from typing import Any, Dict


def send_template(*, idempotency_key: str, template_id: str, placeholders: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "queued",
        "template_id": template_id,
        "idempotency_key": idempotency_key,
        "rendered_preview": {key: str(value) for key, value in placeholders.items()},
    }


__all__ = ["send_template"]
