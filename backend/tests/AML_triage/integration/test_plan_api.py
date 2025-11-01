import json
from pathlib import Path

from fastapi.testclient import TestClient

from AML_triage.api.router import create_app


client = TestClient(create_app())


def test_plan_endpoint_returns_plan():
    payload = json.loads(Path("backend/src/AML_triage/fixtures/scenarios/sus_geo_beh.json").read_text(encoding="utf-8"))
    response = client.post("/triage/plan", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["corridor_risk"] == "HIGH"
    assert any(action["action_id"] == "PLACE_SOFT_HOLD" for action in body["recommended_actions"])
    assert body["approvals_required"]


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert "schema_version" in body
