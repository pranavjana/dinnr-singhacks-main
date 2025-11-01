import json
from pathlib import Path

import pytest

from AML_triage.core.plan_builder import PlanBuilder


@pytest.fixture
def sus_payload() -> dict:
    fixture_path = Path("backend/src/AML_triage/fixtures/scenarios/sus_geo_beh.json")
    return json.loads(fixture_path.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_plan_builder_generates_actions(sus_payload):
    builder = PlanBuilder()
    plan = await builder.build_plan(sus_payload)

    assert plan["summary"]["action_counts"]
    assert plan["summary"]["source_action_ids"] == sus_payload["action_ids"]
    recommended_ids = [action["action_id"] for action in plan["recommended_actions"]]
    assert recommended_ids == sus_payload["action_ids"]
