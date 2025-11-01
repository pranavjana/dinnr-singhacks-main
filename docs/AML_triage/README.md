# AML Triage Service (Hackathon Demo)

Operational notes for the post-screening AML triage microservice.

## Assumptions

- Groq access key is provided via `GROQ_API_KEY`; offline cassette mode falls back to deterministic policy outputs when unset.
- Screening results conform to the contract registry (`backend/src/AML_triage/contracts/`) and can evolve by dropping new `screening_result.v*.json` files without code changes.
- Communication templates are edited via YAML files in `backend/src/AML_triage/templates/action_templates/`; only whitelisted actions/templates are referenced in plans.
- Plans, approvals, and feedback are persisted locally in SQLite (`backend/logs/aml_triage.db`) with immutable JSON logs co-located in the same folder.

## Runbook

1. Create and activate a Python 3.11 virtualenv inside `backend/`.
2. Install dependencies: `pip install -r requirements.txt` (and optionally `-r requirements-dev.txt`).
3. Copy the sample configuration:
   ```bash
   cp src/AML_triage/config/app.example.yaml src/AML_triage/config/app.yaml
   ```
4. Launch the service via Makefile:
   ```bash
   make -C backend run-dev
   ```
5. Execute demo flow:
   ```bash
   curl -s -X POST localhost:8000/triage/plan \
     -H "content-type: application/json" \
     -d @backend/src/AML_triage/fixtures/scenarios/sus_geo_beh.json | jq .
   ```
6. Submit feedback:
   ```bash
   curl -s -X POST localhost:8000/feedback \
     -H "content-type: application/json" \
     -d '{"plan_id":"<from previous response>","label":"good_sus","action_fit":0.9,"reviewer_id_hash":"hash:demo"}'
   ```

## Updating Contracts & Templates

- **Contract Registry**: add new schema versions under `backend/src/AML_triage/contracts/` (e.g., `screening_result.v2.json`) and update `APP_SCHEMA_VERSION` env variable to opt-in. Aliases belong in `aliases.yaml` to keep prompts consistent without code edits.
- **Template Library**: update `templates/index.json` to reference new template IDs then add YAML descriptors in `templates/action_templates/`. Regenerate summaries by restarting the service.

## Contents

- `api_examples/`: curl and Postman samples (populate once endpoints stabilise).
- `runbook.md`: optional extended troubleshooting guide (TBD).

For deeper setup instructions refer to `specs/004-post-screening-aml-triage/quickstart.md`.
