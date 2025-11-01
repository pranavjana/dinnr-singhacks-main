import json
from pathlib import Path

from fastapi.testclient import TestClient

from AML_triage.api.router import create_app


client = TestClient(create_app())


def test_feedback_endpoint_accepts_payload():
    payload = json.loads(Path("backend/src/AML_triage/fixtures/scenarios/sus_geo_beh.json").read_text(encoding="utf-8"))
    plan_response = client.post("/triage/plan", json=payload)
    plan_id = plan_response.json()["plan_id"]

    resp = client.post(
        "/feedback",
        json={
            "plan_id": plan_id,
            "label": "good_sus",
            "action_fit": 0.9,
            "reviewer_id_hash": "hash:reviewer",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
