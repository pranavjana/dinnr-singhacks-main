"\"\"\"Lightweight JSON-backed store for manual compliance rules.\"\"\""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)

_STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "manual_rules.json"


def _ensure_store_dir() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _read_store() -> list[dict[str, Any]]:
    _ensure_store_dir()
    if not _STORE_PATH.exists():
        return []
    try:
        with _STORE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, list):
                return data
    except Exception as exc:
        logger.warning("Failed to read manual rule store", error=str(exc))
    return []


def _write_store(rules: Iterable[dict[str, Any]]) -> None:
    _ensure_store_dir()
    serialized = list(rules)
    with _STORE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(serialized, handle, indent=2, sort_keys=True)


def list_manual_rules() -> list[dict[str, Any]]:
    """Return all stored manual rules."""
    return _read_store()


def get_manual_rule(rule_id: str) -> dict[str, Any] | None:
    """Fetch a manual rule by id."""
    for rule in _read_store():
        if rule.get("id") == rule_id:
            return rule
    return None


def save_manual_rule(rule_payload: dict[str, Any]) -> str:
    """Insert a new manual rule into the store."""
    rules = _read_store()
    rule_id = rule_payload.get("id") or str(uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    rule_data = dict(rule_payload.get("rule_data") or {})
    if "applies_to" not in rule_data:
        applies_to = rule_payload.get("applies_to") or []
        if isinstance(applies_to, list):
            rule_data["applies_to"] = applies_to
    if "source_text" not in rule_data and rule_payload.get("source_text"):
        rule_data["source_text"] = rule_payload.get("source_text")

    record = {
        "id": rule_id,
        "created_at": rule_payload.get("created_at") or now_iso,
        "updated_at": rule_payload.get("updated_at") or now_iso,
        "rule_type": rule_payload.get("rule_type", "manual"),
        "jurisdiction": rule_payload.get("jurisdiction"),
        "regulator": rule_payload.get("regulator"),
        "description": rule_payload.get("description"),
        "rule_data": rule_data,
        "extraction_confidence": rule_payload.get("extraction_confidence", 0.9),
        "effective_date": rule_payload.get("effective_date"),
        "circular_number": rule_payload.get("circular_number"),
        "validation_status": rule_payload.get("validation_status", "pending"),
        "is_active": rule_payload.get("is_active", True),
        "source": "manual-store",
    }

    existing_idx = next((idx for idx, item in enumerate(rules) if item.get("id") == rule_id), None)
    if existing_idx is not None:
        rules[existing_idx] = record
    else:
        rules.append(record)

    _write_store(rules)
    logger.info("Manual rule stored locally", rule_id=rule_id)
    return rule_id


def update_manual_rule(rule_id: str, updates: dict[str, Any]) -> bool:
    """Apply updates to an existing manual rule."""
    rules = _read_store()
    for idx, rule in enumerate(rules):
        if rule.get("id") == rule_id:
            updated = {**rule, **updates, "updated_at": updates.get("updated_at") or datetime.now(timezone.utc).isoformat()}
            rules[idx] = updated
            _write_store(rules)
            logger.info("Manual rule updated locally", rule_id=rule_id)
            return True
    return False
