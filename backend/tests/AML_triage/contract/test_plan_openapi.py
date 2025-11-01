from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from AML_triage.api.router import create_app


def test_openapi_matches_contract_subset():
    client = TestClient(create_app())
    live = client.get("/openapi.json").json()

    contract_path = Path("specs/004-post-screening-aml-triage/contracts/openapi.yaml")
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

    assert set(contract["paths"].keys()).issubset(set(live["paths"].keys()))
    assert contract["components"]["schemas"]["Plan"]["type"] == "object"
