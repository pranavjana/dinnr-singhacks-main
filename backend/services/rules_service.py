"""
Service for interfacing with feature 003 (rule extraction).
Provides access to active AML compliance rules.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional
from uuid import UUID

import httpx

try:
    # Try backend-prefixed imports first (running from parent directory)
    from backend.core.config import settings
    from backend.core.observability import get_logger
except ModuleNotFoundError:
    # Fall back to relative imports (running from backend directory)
    from core.config import settings
    from core.observability import get_logger

logger = get_logger(__name__)


class ComplianceRule:
    """
    Represents an AML compliance rule from feature 003.

    Phase 2 uses a JSON-backed cache while the database integration
    (compliance_rules table) is still in progress. The schema mirrors
    what the Supabase table would return.
    """

    def __init__(
        self,
        rule_id: UUID,
        rule_type: str,
        jurisdiction: str | None,
        regulator: str | None,
        severity: str,
        description: str,
        rule_data: dict[str, Any],
    ):
        self.rule_id = rule_id
        self.rule_type = rule_type
        self.jurisdiction = (jurisdiction or "").upper() or None
        self.regulator = regulator or None
        self.severity = severity
        self.description = description
        self.rule_data = rule_data or {}

    @property
    def applies_globally(self) -> bool:
        """Return True when no jurisdiction filter is specified."""
        if self.jurisdiction is None:
            return True
        return self.jurisdiction in {"*", "GLOBAL", "ALL"}


class RulesService:
    """
    Service for retrieving and applying AML compliance rules.

    Interfaces with feature 003 (langgraph-rule-extraction) to get
    active compliance rules from regulatory circulars.
    """

    def __init__(self) -> None:
        self.logger = logger
        self._rules_cache: list[ComplianceRule] = []
        self._cache_expiry: float = 0.0
        self._cache_ttl_seconds: int = getattr(settings, "rules_cache_ttl_seconds", 60)

    async def get_active_rules(
        self,
        jurisdiction: Optional[str] = None,
        regulator: Optional[str] = None,
    ) -> List[ComplianceRule]:
        """
        Retrieve active compliance rules.

        Args:
            jurisdiction: Filter by jurisdiction (e.g., 'SG', 'HK', 'CH')
            regulator: Filter by regulator (e.g., 'MAS', 'HKMA', 'FINMA')

        Returns:
            List of active compliance rules
        """
        jurisdiction_upper = jurisdiction.upper() if jurisdiction else None
        regulator_upper = regulator.upper() if regulator else None

        rules = await self._load_rules_from_source()
        return [
            rule
            for rule in rules
            if self._matches_jurisdiction(rule, jurisdiction_upper)
            and self._matches_regulator(rule, regulator_upper)
        ]

    async def get_rule_by_id(self, rule_id: UUID) -> Optional[ComplianceRule]:
        """
        Retrieve a specific rule by ID.

        Args:
            rule_id: UUID of the compliance rule

        Returns:
            ComplianceRule if found, None otherwise
        """
        self.logger.info("fetching_rule_by_id - rule_id=%s", str(rule_id))

        rules = await self._load_rules_from_source()
        for rule in rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    async def evaluate_payment_against_rules(
        self,
        payment_data: dict,
        rules: Iterable[ComplianceRule],
    ) -> List[dict]:
        """
        Evaluate a payment against a list of compliance rules.

        Args:
            payment_data: Payment transaction data
            rules: List of rules to check

        Returns:
            List of triggered rules with evidence
        """
        # The LangGraph node performs evaluation; this method is kept for API parity.
        # It simply returns an empty list until feature 003 needs it directly.
        rule_count = len(list(rules))
        self.logger.debug(
            "evaluate_payment_against_rules_called - rule_count=%s",
            rule_count,
        )
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _matches_jurisdiction(
        self,
        rule: ComplianceRule,
        jurisdiction: Optional[str],
    ) -> bool:
        if jurisdiction is None or rule.applies_globally:
            return True
        return rule.jurisdiction == jurisdiction

    def _matches_regulator(
        self,
        rule: ComplianceRule,
        regulator: Optional[str],
    ) -> bool:
        if regulator is None or not rule.regulator:
            return True
        return rule.regulator.upper() == regulator

    async def _load_rules_from_source(self) -> list[ComplianceRule]:
        """
        Load rules from JSON file, caching between calls.
        """
        now = time.time()
        if self._rules_cache and now < self._cache_expiry:
            return self._rules_cache

        rules: list[ComplianceRule] = []

        file_rules = self._load_rules_from_file()
        if file_rules:
            rules = file_rules
        else:
            supabase_rules = await self._fetch_rules_from_supabase()
            rules = supabase_rules

        self._rules_cache = rules
        self._cache_expiry = now + self._cache_ttl_seconds
        return rules

    async def _fetch_rules_from_supabase(self) -> list[ComplianceRule]:
        """
        Attempt to fetch rules from Supabase REST endpoint.
        """
        supabase_url = getattr(settings, "supabase_url", "")
        supabase_key = getattr(settings, "supabase_key", "")

        if not supabase_url or not supabase_key:
            return []

        rest_endpoint = supabase_url.rstrip("/") + "/rest/v1/compliance_rules"
        params = {
            "select": "*",
            "validation_status": "eq.validated",
            "is_active": "eq.true",
            "order": "effective_date.desc.nullslast",
        }
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    rest_endpoint,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # pragma: no cover - external dependency
            self.logger.warning(
                "supabase_rules_fetch_failed - error=%s",
                str(exc),
            )
            return []

        parsed_rules: list[ComplianceRule] = []
        for row in data:
            try:
                parsed_rules.append(self._parse_rule_record(row))
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.error(
                    "invalid_supabase_rule_skipped - error=%s, record=%s",
                    str(exc),
                    row,
                )

        if parsed_rules:
            self.logger.info(
                "compliance_rules_loaded_supabase - count=%s",
                len(parsed_rules),
            )

        return parsed_rules

    def _load_rules_from_file(self) -> list[ComplianceRule]:
        rules_path = self._resolve_rules_path()

        if not rules_path.exists():
            self.logger.warning(
                "compliance_rules_file_missing - path=%s",
                str(rules_path),
            )
            return []

        try:
            with rules_path.open("r", encoding="utf-8") as handle:
                raw_rules = json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error(
                "failed_to_load_rules_file - path=%s, error=%s",
                str(rules_path),
                str(exc),
            )
            self._rules_cache = []
            return self._rules_cache

        now = datetime.now(tz=timezone.utc)
        parsed_rules: list[ComplianceRule] = []

        for raw_rule in raw_rules:
            try:
                if not raw_rule.get("is_active", True):
                    continue

                validation_status = raw_rule.get("validation_status")
                if validation_status and validation_status.lower() != "validated":
                    continue

                expiry_date = self._parse_datetime(raw_rule.get("expiry_date"))
                if expiry_date and expiry_date <= now:
                    continue

                rule_id = UUID(str(raw_rule["rule_id"]))
                description = raw_rule.get("description") or raw_rule.get("rule_type", "rule")
                rule_data = raw_rule.get("rule_data") or {}

                parsed_rules.append(
                    ComplianceRule(
                        rule_id=rule_id,
                        rule_type=str(raw_rule.get("rule_type")),
                        jurisdiction=raw_rule.get("jurisdiction"),
                        regulator=raw_rule.get("regulator"),
                        severity=str(raw_rule.get("severity", "low")),
                        description=description,
                        rule_data=rule_data,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                self.logger.error(
                    "invalid_rule_record_skipped - error=%s, record=%s",
                    str(exc),
                    raw_rule,
                )

        self.logger.info(
            "compliance_rules_loaded - path=%s, count=%s",
            str(rules_path),
            len(parsed_rules),
        )

        return parsed_rules

    def _resolve_rules_path(self) -> Path:
        """
        Resolve the filesystem path to the compliance rules JSON file.
        """
        configured_path = getattr(settings, "rules_data_path", None)

        if configured_path:
            path = Path(configured_path).expanduser()
            if not path.is_absolute():
                base_dir = Path(__file__).resolve().parent
                path = (base_dir / path).resolve()
            return path

        # Default to backend/services/data/compliance_rules.json
        return (
            Path(__file__).resolve().parent
            / "data"
            / "compliance_rules.json"
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """
        Parse ISO-8601 timestamps, returning timezone-aware datetime.
        """
        if not value:
            return None

        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        try:
            text = str(value).strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _parse_rule_record(record: dict[str, Any]) -> ComplianceRule:
        """
        Convert a raw record (from Supabase or JSON) into ComplianceRule.
        """
        rule_data = record.get("rule_data") or {}
        severity = (
            record.get("severity")
            or rule_data.get("violation_severity")
            or rule_data.get("severity")
            or "medium"
        )
        description = (
            record.get("description")
            or record.get("summary")
            or record.get("rule_type", "rule")
        )

        return ComplianceRule(
            rule_id=UUID(str(record.get("rule_id") or record["id"])),
            rule_type=str(record.get("rule_type")),
            jurisdiction=record.get("jurisdiction"),
            regulator=record.get("regulator"),
            severity=str(severity),
            description=description,
            rule_data=rule_data,
        )


# Global service instance
rules_service = RulesService()
"""
Rules service for AML compliance rules management.
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class RulesService:
    """Service for managing and retrieving AML compliance rules."""

    def __init__(self):
        """Initialize rules service."""
        self.rules_cache: Dict[str, List[Dict[str, Any]]] = {}

    async def get_active_rules(
        self, jurisdiction: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get active AML rules for a jurisdiction.

        Args:
            jurisdiction: Optional jurisdiction code (e.g., 'HK', 'SG', 'CH')

        Returns:
            List of active rule dictionaries
        """
        logger.info(f"Fetching active rules for jurisdiction: {jurisdiction}")

        # Default rules for all jurisdictions
        default_rules = [
            {
                "rule_id": "STRUCT_001",
                "rule_type": "structuring",
                "description": "Detect structuring patterns below reporting threshold",
                "threshold": 10000,
                "enabled": True,
            },
            {
                "rule_id": "VELOCITY_001",
                "rule_type": "velocity",
                "description": "Detect unusual transaction velocity",
                "threshold": 5,
                "enabled": True,
            },
            {
                "rule_id": "HIGHRISK_001",
                "rule_type": "high_risk_jurisdiction",
                "description": "Flag transactions to/from high-risk jurisdictions",
                "enabled": True,
            },
            {
                "rule_id": "PEP_001",
                "rule_type": "pep",
                "description": "Enhanced monitoring for PEP transactions",
                "enabled": True,
            },
        ]

        # Add jurisdiction-specific rules if needed
        if jurisdiction:
            jurisdiction_rules = self._get_jurisdiction_rules(jurisdiction)
            return default_rules + jurisdiction_rules

        return default_rules

    def _get_jurisdiction_rules(self, jurisdiction: str) -> List[Dict[str, Any]]:
        """
        Get jurisdiction-specific rules.

        Args:
            jurisdiction: Jurisdiction code

        Returns:
            List of jurisdiction-specific rules
        """
        jurisdiction_map = {
            "HK": [
                {
                    "rule_id": "HK_001",
                    "rule_type": "hkma_reporting",
                    "description": "HKMA suspicious transaction reporting",
                    "enabled": True,
                }
            ],
            "SG": [
                {
                    "rule_id": "SG_001",
                    "rule_type": "mas_reporting",
                    "description": "MAS suspicious transaction reporting",
                    "enabled": True,
                }
            ],
            "CH": [
                {
                    "rule_id": "CH_001",
                    "rule_type": "finma_reporting",
                    "description": "FINMA suspicious transaction reporting",
                    "enabled": True,
                }
            ],
        }

        return jurisdiction_map.get(jurisdiction.upper(), [])


# Global service instance
rules_service = RulesService()
