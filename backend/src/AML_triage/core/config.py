"""Configuration loading utilities for the AML triage service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError


class AppPaths(BaseModel):
    """Physical locations for contracts, templates, fixtures, and logs."""

    contracts_dir: Path
    templates_dir: Path
    fixtures_dir: Path
    logs_dir: Path


class HttpSettings(BaseModel):
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)


class LLMSettings(BaseModel):
    model_id: str = Field(default="llama-3.3-70b-versatile", min_length=1)
    temperature: float = Field(default=0.1, ge=0, le=1)
    max_output_tokens: int = Field(default=2048, gt=0)


class Settings(BaseModel):
    """Global application settings sourced from YAML + environment overrides."""

    schema_version: str = Field(default="v1", pattern=r"^v[0-9]+$")
    strict_fields: bool = True
    template_top_k: int = Field(default=2, ge=1)
    offline_mode: bool = True
    paths: AppPaths
    http: HttpSettings = Field(default_factory=HttpSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @property
    def contracts_dir(self) -> Path:
        return self.paths.contracts_dir

    @property
    def templates_dir(self) -> Path:
        return self.paths.templates_dir

    @property
    def fixtures_dir(self) -> Path:
        return self.paths.fixtures_dir

    @property
    def logs_dir(self) -> Path:
        return self.paths.logs_dir


class SettingsError(RuntimeError):
    """Raised when configuration cannot be loaded."""


def _load_yaml_config() -> Dict[str, Any]:
    config_path = os.getenv("APP_CONFIG", "backend/src/AML_triage/config/app.yaml")
    path = Path(config_path)

    if not path.exists():
        raise SettingsError(f"APP_CONFIG path not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    # Allow environment overrides for path values.
    paths: Dict[str, Any] = data.get("paths", {})
    data["paths"] = {
        "contracts_dir": Path(os.getenv("APP_CONTRACTS_DIR", paths.get("contracts_dir", "backend/src/AML_triage/contracts"))),
        "templates_dir": Path(os.getenv("APP_TEMPLATES_DIR", paths.get("templates_dir", "backend/src/AML_triage/templates"))),
        "fixtures_dir": Path(os.getenv("APP_FIXTURES_DIR", paths.get("fixtures_dir", "backend/src/AML_triage/fixtures"))),
        "logs_dir": Path(os.getenv("APP_LOGS_DIR", paths.get("logs_dir", "backend/logs"))),
    }

    # Boolean overrides via env
    if "APP_SCHEMA_VERSION" in os.environ:
        data["schema_version"] = os.environ["APP_SCHEMA_VERSION"]

    if "STRICT_FIELDS" in os.environ:
        data["strict_fields"] = os.environ["STRICT_FIELDS"].lower() in {"1", "true", "yes"}

    if "TEMPLATE_TOP_K" in os.environ:
        data["template_top_k"] = int(os.environ["TEMPLATE_TOP_K"])

    if "OFFLINE_MODE" in os.environ:
        data["offline_mode"] = os.environ["OFFLINE_MODE"].lower() in {"1", "true", "yes"}

    if "MODEL_ID" in os.environ:
        llm: Dict[str, Any] = data.get("llm", {})
        llm["model_id"] = os.environ["MODEL_ID"]
        data["llm"] = llm

    if "LLM_TEMPERATURE" in os.environ:
        llm = data.get("llm", {})
        llm["temperature"] = float(os.environ["LLM_TEMPERATURE"])
        data["llm"] = llm

    if "LLM_MAX_TOKENS" in os.environ:
        llm = data.get("llm", {})
        llm["max_output_tokens"] = int(os.environ["LLM_MAX_TOKENS"])
        data["llm"] = llm

    return data


_CACHED_SETTINGS: Optional[Settings] = None


def load_settings(force_reload: bool = False) -> Settings:
    """Load application settings and cache the result."""

    global _CACHED_SETTINGS

    if _CACHED_SETTINGS is not None and not force_reload:
        return _CACHED_SETTINGS

    raw = _load_yaml_config()

    try:
        settings = Settings.model_validate(raw)
    except ValidationError as exc:
        raise SettingsError(f"Invalid configuration: {exc}") from exc

    # Ensure directories exist at runtime (except templates, which may be packaged)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    _CACHED_SETTINGS = settings
    return settings


__all__ = [
    "Settings",
    "SettingsError",
    "load_settings",
]
