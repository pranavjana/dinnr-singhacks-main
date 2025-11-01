from pathlib import Path

from fastapi.testclient import TestClient

from AML_triage.api.router import create_app


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_report_endpoint_returns_text(tmp_path, monkeypatch):
    summary = (FIXTURES_DIR / "case_summary.txt").read_text(encoding="utf-8")

    # Force offline mode to reuse deterministic cassette writing
    monkeypatch.setenv("APP_CONFIG", "src/AML_triage/config/app.yaml")
    monkeypatch.setenv("OFFLINE_MODE", "true")
    monkeypatch.setenv("APP_FIXTURES_DIR", str(tmp_path / "fixtures"))

    app = create_app()
    client = TestClient(app)
    response = client.post("/triage/plan", data=summary, headers={"content-type": "text/plain"})

    assert response.status_code == 200
    assert "Recommended action" in response.text or "Offline mode" in response.text
