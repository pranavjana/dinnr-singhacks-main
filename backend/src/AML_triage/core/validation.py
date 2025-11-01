"""Validation helpers for screening inputs and generated plans."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator, ValidationError

from .config import Settings, load_settings
from .contracts import AliasMap, load_alias_map, load_screening_schema, normalise_aliases


class SchemaValidationError(RuntimeError):
    """Raised when payloads fail schema validation."""

    def __init__(self, message: str, *, errors: List[Dict[str, Any]] | None = None):
        super().__init__(message)
        self.errors = errors or []


def _build_validator(schema: Dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema)


def validate_screening_result(
    payload: Dict[str, Any],
    *,
    settings: Settings | None = None,
) -> Tuple[Dict[str, Any], str, List[str]]:
    """Validate and normalise an incoming screening result.

    Returns the normalised payload, schema version, and list of aliases applied.
    """

    settings = settings or load_settings()
    alias_map = load_alias_map(settings)
    schema_version = settings.schema_version
    schema = load_screening_schema(schema_version, settings)

    normalised = normalise_aliases(payload, alias_map, strict=settings.strict_fields)

    validator = _build_validator(schema)
    errors = sorted(validator.iter_errors(normalised), key=lambda err: err.path)

    if errors:
        formatted = [
            {
                "path": list(error.path),
                "message": error.message,
                "validator": error.validator,
            }
            for error in errors
        ]
        raise SchemaValidationError("ScreeningResult failed validation", errors=formatted)

    aliases_used = [alias for alias in payload.keys() if alias != alias_map.resolve_key(alias)]

    return normalised, schema_version, aliases_used


def hash_payload(payload: Dict[str, Any]) -> str:
    """Stable SHA256 hash of a JSON-like dict for deduplication."""

    import json

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "SchemaValidationError",
    "validate_screening_result",
    "hash_payload",
]
