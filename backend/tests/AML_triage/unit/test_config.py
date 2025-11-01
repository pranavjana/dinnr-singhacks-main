import os
from pathlib import Path

import pytest

from AML_triage.core.config import SettingsError, load_settings


def test_load_settings_defaults(monkeypatch, tmp_path):
    config_file = tmp_path / "app.yaml"
    config_file.write_text(
        """
schema_version: v2
strict_fields: false
paths:
  contracts_dir: backend/src/AML_triage/contracts
  templates_dir: backend/src/AML_triage/templates
  fixtures_dir: backend/src/AML_triage/fixtures
  logs_dir: backend/logs
""",
        encoding="utf-8",
    )

    monkeypatch.setenv("APP_CONFIG", str(config_file))
    settings = load_settings(force_reload=True)
    assert settings.schema_version == "v2"
    assert settings.strict_fields is False


def test_missing_config_raises(monkeypatch):
    monkeypatch.setenv("APP_CONFIG", "missing.yaml")
    with pytest.raises(SettingsError):
        load_settings(force_reload=True)
