import json
from pathlib import Path

from fastapi.testclient import TestClient

from AML_triage.api.router import create_app


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    fixture_path = FIXTURES_DIR / name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_report_endpoint_returns_text(tmp_path, monkeypatch):
    payload = load_fixture("llm3_payload_sample.json")

    # Force offline mode to reuse deterministic cassette writing
    monkeypatch.setenv("APP_CONFIG", "src/AML_triage/config/app.yaml")
    monkeypatch.setenv("OFFLINE_MODE", "true")

    app = create_app()
    client = TestClient(app)
    response = client.post("/triage/plan", json=payload)

    assert response.status_code == 200
    assert "Recommended action" in response.text or "Offline mode" in response.text
