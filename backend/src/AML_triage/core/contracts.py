"""Contract registry loader and alias normalisation utilities."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from .config import Settings, load_settings


class ContractNotFoundError(RuntimeError):
    """Raised when a requested contract schema is missing."""


class AliasMap:
    """In-memory alias map supporting nested keys (dot notation)."""

    def __init__(self, aliases: Dict[str, Iterable[str]]):
        self._reverse: Dict[str, str] = {}
        for canonical, candidates in aliases.items():
            for alias in candidates:
                self._reverse[alias] = canonical

    def resolve_key(self, key: str) -> str:
        return self._reverse.get(key, key)

    def canonical_items(self) -> Iterable[str]:
        return set(self._reverse.values())


def _schema_path(contract_dir: Path, version: str) -> Path:
    filename = f"screening_result.{version}.json"
    return contract_dir / filename


@lru_cache(maxsize=4)
def _load_alias_map(contract_dir: Path) -> AliasMap:
    path = contract_dir / "aliases.yaml"

    if not path.exists():
        return AliasMap({})

    with path.open("r", encoding="utf-8") as handle:
        raw: Dict[str, Any] = yaml.safe_load(handle) or {}

    # Normalise values to lists
    canonical: Dict[str, Iterable[str]] = {}
    for key, value in raw.items():
        if isinstance(value, str):
            canonical[key] = [value]
        else:
            canonical[key] = value or []

    return AliasMap(canonical)


def load_alias_map(settings: Settings | None = None) -> AliasMap:
    settings = settings or load_settings()
    return _load_alias_map(settings.contracts_dir)


@lru_cache(maxsize=4)
def _load_screening_schema(contract_dir: Path, version: str) -> Dict[str, Any]:
    path = _schema_path(contract_dir, version)

    if not path.exists():
        raise ContractNotFoundError(f"no schema found for version {version} at {path}")

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_screening_schema(version: str, settings: Settings | None = None) -> Dict[str, Any]:
    settings = settings or load_settings()
    return _load_screening_schema(settings.contracts_dir, version)


def normalise_aliases(payload: Dict[str, Any], alias_map: AliasMap, *, strict: bool) -> Dict[str, Any]:
    """Return a copy of ``payload`` with alias keys replaced by canonical keys."""

    def _transform(value: Any, canonical_prefix: str) -> Any:
        if isinstance(value, dict):
            result: Dict[str, Any] = {}
            for raw_key, raw_val in value.items():
                dotted = f"{canonical_prefix}.{raw_key}" if canonical_prefix else raw_key
                canonical_dotted = alias_map.resolve_key(dotted)

                # Derive relative path from the parent prefix so we don't duplicate segments.
                if canonical_prefix and canonical_dotted.startswith(f"{canonical_prefix}."):
                    relative = canonical_dotted[len(canonical_prefix) + 1 :]
                else:
                    relative = canonical_dotted

                segments = relative.split(".") if relative else []
                if not segments:
                    continue

                target = result
                for segment in segments[:-1]:
                    target = target.setdefault(segment, {})
                target[segments[-1]] = _transform(raw_val, canonical_dotted)
            return result

        if isinstance(value, list):
            return [_transform(item, canonical_prefix) for item in value]

        return value

    normalised = _transform(payload, "")

    if strict:
        # Ensure no unexpected top-level keys remain after alias resolution.
        for key in list(normalised.keys()):
            alias_map.resolve_key(key)

    return normalised


__all__ = [
    "AliasMap",
    "ContractNotFoundError",
    "load_alias_map",
    "load_screening_schema",
    "normalise_aliases",
]
