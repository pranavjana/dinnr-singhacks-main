from pathlib import Path

import pytest

from AML_triage.core import contracts
from AML_triage.core.config import Settings, load_settings


@pytest.fixture(scope="module")
def settings(tmp_path_factory) -> Settings:
    settings = load_settings(force_reload=True)
    return settings


def test_load_screening_schema(settings: Settings):
    schema = contracts.load_screening_schema(settings.schema_version, settings)
    assert schema["title"] == "ScreeningResult"


def test_alias_normalisation(settings: Settings):
    alias_map = contracts.load_alias_map(settings)
    payload = {
        "schemaVersion": "v1",
        "screening_decision": "PASS",
        "ruleCodes": ["TEST_RULE"],
        "transfer_corridor": {
            "originCountry": "SGP",
            "destinationCountry": "SGP",
            "transfer_channel": "SWIFT",
            "transfer_currency": "SGD",
        },
        "transfer_amount": 1000,
    }

    normalised = contracts.normalise_aliases(payload, alias_map, strict=False)
    assert normalised["schema_version"] == "v1"
    assert normalised["decision"] == "PASS"
    assert normalised["corridor"]["origin_country"] == "SGP"
