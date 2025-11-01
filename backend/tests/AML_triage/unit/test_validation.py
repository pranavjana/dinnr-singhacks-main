import pytest

from AML_triage.core.validation import SchemaValidationError, validate_screening_result


def test_validate_screening_result_success():
    payload = {
        "schema_version": "v1",
        "decision": "PASS",
        "rule_codes": ["TEST"],
        "corridor": {
            "origin_country": "SGP",
            "destination_country": "SGP",
            "channel": "SWIFT",
            "currency": "SGD",
        },
        "amount": 100,
    }

    normalised, schema_version, aliases = validate_screening_result(payload)
    assert normalised["decision"] == "PASS"
    assert schema_version == "v1"
    assert aliases == []


def test_validate_screening_result_failure():
    payload = {
        "schema_version": "v1",
        "decision": "INVALID",
        "rule_codes": [],
        "corridor": {},
        "amount": -1,
    }

    with pytest.raises(SchemaValidationError):
        validate_screening_result(payload)
