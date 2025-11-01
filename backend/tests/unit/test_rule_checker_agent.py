import pytest
from uuid import uuid4

from backend.agents.aml_monitoring.rule_checker_agent import check_rules_node


@pytest.mark.asyncio
async def test_check_rules_node_triggers_threshold_rule():
    state = {
        "payment": {
            "originator_name": "Test Originator",
            "originator_account": "SG123456789",
            "originator_country": "SG",
            "beneficiary_name": "Test Beneficiary",
            "beneficiary_account": "US987654321",
            "beneficiary_country": "US",
            "amount": 25000.0,
            "currency": "USD",
            "transaction_date": "2025-11-01T10:30:00Z",
            "value_date": "2025-11-01T10:30:00Z",
            "swift_message_type": "MT103",
            "sanctions_screening_result": "PASS",
            "pep_screening_result": "PASS",
        },
        "payment_id": uuid4(),
        "trace_id": uuid4(),
    }

    result = await check_rules_node(state)

    assert result["rule_score"] > 0, "Expected non-zero rule score when threshold rule violated"
    assert result["triggered_rules"], "Expected at least one triggered rule"
    assert any(
        rule["rule_type"] == "transaction_amount_threshold"
        for rule in result["triggered_rules"]
    ), "Threshold rule should be triggered for large SG transaction"
