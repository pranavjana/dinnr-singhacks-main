"""SQLite-backed persistence and audit logging for AML triage."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel

from .config import Settings, load_settings


CREATE_PLANS_TABLE = """
CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    input_hash TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CREATE_APPROVALS_TABLE = """
CREATE TABLE IF NOT EXISTS approvals (
    plan_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    approver_role TEXT NOT NULL,
    status TEXT NOT NULL,
    decided_at TEXT,
    reviewer_id_hash TEXT,
    PRIMARY KEY(plan_id, action_id)
);
"""

CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    plan_id TEXT NOT NULL,
    label TEXT NOT NULL,
    action_fit REAL,
    reviewer_id_hash TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(plan_id, reviewer_id_hash)
);
"""


class StorageError(RuntimeError):
    """Raised for persistence failures."""


class FeedbackRecord(BaseModel):
    plan_id: str
    label: str
    action_fit: float | None = None
    reviewer_id_hash: str
    notes: str | None = None
    created_at: datetime


class Storage:
    """Thin SQLite wrapper for plans, approvals, and feedback records."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.db_path = self._database_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _database_path(self) -> Path:
        return self.settings.logs_dir / "aml_triage.db"

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialise(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_PLANS_TABLE)
            cursor.execute(CREATE_APPROVALS_TABLE)
            cursor.execute(CREATE_FEEDBACK_TABLE)

    def _log_event(self, event: str, details: Dict[str, Any]) -> None:
        log_path = self.settings.logs_dir / "aml_triage.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

    def plan_exists(self, input_hash: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT payload FROM plans WHERE input_hash = ? ORDER BY created_at DESC LIMIT 1",
                (input_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def save_plan(self, plan_payload: Dict[str, Any]) -> None:
        plan_id = plan_payload.get("plan_id")
        if not plan_id:
            raise StorageError("plan payload missing plan_id")
        payload_json = json.dumps(plan_payload, separators=(",", ":"))
        input_hash = plan_payload.get("input_hash")
        schema_version = plan_payload.get("schema_version")
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO plans(plan_id, input_hash, schema_version, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (plan_id, input_hash, schema_version, payload_json, created_at),
            )

            approvals = plan_payload.get("approvals_required", [])
            for approval in approvals:
                cursor.execute(
                    "INSERT OR REPLACE INTO approvals(plan_id, action_id, approver_role, status, decided_at, reviewer_id_hash) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        plan_id,
                        approval.get("action_id"),
                        approval.get("approver_role"),
                        approval.get("status", "PENDING"),
                        approval.get("decided_at"),
                        approval.get("reviewer_id_hash"),
                    ),
                )

        self._log_event(
            "PLAN_EMITTED",
            {
                "plan_id": plan_id,
                "input_hash": input_hash,
                "schema_version": schema_version,
            },
        )

    def record_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO feedback(plan_id, label, action_fit, reviewer_id_hash, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.plan_id,
                    record.label,
                    record.action_fit,
                    record.reviewer_id_hash,
                    record.notes,
                    record.created_at.isoformat(),
                ),
            )
        self._log_event(
            "FEEDBACK_RECORDED",
            {
                "plan_id": record.plan_id,
                "label": record.label,
                "reviewer_id_hash": record.reviewer_id_hash,
            },
        )
        return record

    def fetch_feedback_snippets(
        self, *, rule_codes: Iterable[str], corridor_risk: str, decision: str, limit: int = 3
    ) -> List[FeedbackRecord]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT plan_id, label, action_fit, reviewer_id_hash, notes, created_at "
                "FROM feedback ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()

        records: List[FeedbackRecord] = []
        for row in rows:
            records.append(
                FeedbackRecord(
                    plan_id=row[0],
                    label=row[1],
                    action_fit=row[2],
                    reviewer_id_hash=row[3],
                    notes=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                )
            )
        return records


__all__ = ["Storage", "StorageError", "FeedbackRecord"]
