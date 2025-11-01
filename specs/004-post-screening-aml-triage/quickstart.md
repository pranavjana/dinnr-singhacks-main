# Quickstart — Post-Screening AML Triage Layer

## 1. Prerequisites
- Python 3.11.x (uv/venv supported)
- `poetry` or `uv` (preferred) for dependency management
- Groq API key (for live runs) exported as `GROQ_API_KEY`; optional when replaying fixtures
- macOS/Linux shell with `make` (for helper targets)

## 2. Environment Setup
```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt  # generates pytest/typing extras
```

Copy configuration template and adjust as needed:
```bash
cp src/AML_triage/config/app.example.yaml src/AML_triage/config/app.yaml
```
- Set `offline_mode: true` to force fixture playback.
- Provide absolute paths for `fixtures_dir`, `templates_dir`, and `contracts_dir` if running outside repo root.

## 3. Running the API
```bash
export APP_CONFIG=backend/src/AML_triage/config/app.yaml
uvicorn AML_triage.api.router:create_app --factory --reload
```

Endpoints:
- `POST /triage/plan` — submit `fixtures/scenarios/*.json` to verify PASS/SUS/FAIL plans.
- `POST /feedback` — send reviewer feedback payload referencing `plan_id`.
- `GET /healthz` — liveness + configuration echo (schema version, strict mode, offline flag).

## 4. Offline vs Live LLM Modes
- **Offline (default for hackathon)**: Set `OFFLINE_MODE=true`; the agent loads Groq cassette responses from `fixtures/groq_captures/`.  
- **Live**: Set `OFFLINE_MODE=false` and export `GROQ_API_KEY`. The agent records new responses for future playback while enforcing JSON schema validation.

## 5. Testing
```bash
pytest backend/tests/AML_triage -m "not slow"
pytest backend/tests/AML_triage -m contract  # runs schemathesis against openapi.yaml
```
- Contract tests fail if generated OpenAPI deviates from `specs/004-post-screening-aml-triage/contracts/openapi.yaml`.
- Integration tests assert policy guardrails, approval gating, and offline replay behaviour.

## 6. Updating Contracts & Templates
- Modify `backend/src/AML_triage/contracts/screening_result.v1.json` and `aliases.yaml`; bump `APP_SCHEMA_VERSION` in config if upgrading.
- Update action catalogue (`templates/action_catalogue.json`) and per-action templates (`templates/action_templates/*.yaml`); rerun `pytest -k template`.
- Record new Groq few-shots by toggling live mode and saving sanitized outputs back into `fixtures/groq_captures/`.

## 7. Observability & Audit
- Structured logs are written to `logs/aml_triage.jsonl`; tail with `jq` or `rg`.
- Prometheus metrics exposed at `/metrics`; configure scrape target in dev docker compose.
- Hashing rules ensure account numbers show last 4 digits only; confirm via logs before demos.
