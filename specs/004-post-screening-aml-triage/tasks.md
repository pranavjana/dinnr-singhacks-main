# Tasks: Post-Screening AML Triage Layer

**Input**: Design documents from `/specs/004-post-screening-aml-triage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bootstrap repository structure, configuration scaffolds, and tooling needed by all stories.

- [ ] T001 Create AML_triage package directories under `backend/src/AML_triage/{api,core,agent,adapters,config,contracts,templates/action_templates,fixtures}` and test roots under `backend/tests/AML_triage/{unit,integration,contract}`  
- [ ] T002 Add `__init__.py` stubs for new packages (`backend/src/AML_triage/__init__.py`, subpackages, and `backend/tests/AML_triage/__init__.py`)  
- [ ] T003 Create `backend/Makefile` with `run` (uvicorn) and `test` (pytest + contract suite) targets wired to AML_triage app  
- [ ] T004 Add `backend/.env.example` capturing `APP_CONFIG`, `GROQ_API_KEY`, `OFFLINE_MODE`, `APP_SCHEMA_VERSION`, `STRICT_FIELDS`, `MODEL_ID` defaults  
- [ ] T005 Populate `backend/requirements.txt` and `backend/requirements-dev.txt` with FastAPI, LangGraph, httpx, structlog, SQLModel, pytest, schemathesis, respx, orjson  
- [ ] T006 Create `backend/src/AML_triage/config/app.example.yaml` with schema_version, strict_fields, template_top_k, fixtures_dir, templates_dir, offline_mode, model_id settings  
- [ ] T007 Scaffold developer documentation stub `docs/AML_triage/README.md` to mirror quickstart checkpoints  

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story implementation.

- [ ] T008 Author `backend/src/AML_triage/contracts/screening_result.v1.json` covering decision, rule_codes, corridor, amount, behavioural patterns, evidence, metadata (additionalProperties=false)  
- [ ] T009 Create `backend/src/AML_triage/contracts/aliases.yaml` mapping common field aliases (e.g., `benefeciary_account` → `beneficiary_account`)  
- [ ] T010 Implement contract registry loader in `backend/src/AML_triage/core/contracts.py` resolving `APP_SCHEMA_VERSION` and alias maps with caching  
- [ ] T011 Implement JSON Schema validator in `backend/src/AML_triage/core/validation.py` that normalizes aliases, enforces `STRICT_FIELDS`, and returns structured error payloads  
- [ ] T012 Create `backend/src/AML_triage/templates/action_catalogue.json` enumerating actions (`CREATE_CASE`, `REQUEST_SOF_DOCS`, `REQUEST_UBO_DOCS`, `PLACE_SOFT_HOLD`, `ESCALATE_L2_AML`, `ROUTE_KYC_OPS`, `FILE_STR_DRAFT`, `SEND_RM_BRIEF`, `SEND_CUSTOMER_DOCREQ`) with `allowed_if`, `requires_approval`, `tool`, `params`  
- [ ] T013 Implement action catalogue service in `backend/src/AML_triage/core/actions.py` to load catalogue, validate entries, and expose guardrail checks  
- [ ] T014 Implement config loader (`Settings`) in `backend/src/AML_triage/core/config.py` reading `app.yaml`, env overrides, and default fallbacks  
- [ ] T015 Implement template registry skeleton in `backend/src/AML_triage/core/templates.py` loading `templates/index.json`, YAML metadata, and returning summary stubs  
- [ ] T016 Implement persistence layer in `backend/src/AML_triage/core/storage.py` for SQLite (plans, approvals, feedback tables) plus append-only JSON audit log writer  
- [ ] T017 Implement observability helpers in `backend/src/AML_triage/core/metrics.py` (Prometheus counters/histograms, structlog context filters, PII masking utilities)  
- [ ] T018 [P] Add unit tests for contract loader & alias normalization in `backend/tests/AML_triage/unit/test_contracts.py`  
- [ ] T019 [P] Add unit tests for validator error handling in `backend/tests/AML_triage/unit/test_validation.py`  
- [ ] T020 [P] Add unit tests for config loader env overrides in `backend/tests/AML_triage/unit/test_config.py`  

**Checkpoint**: Contract registry, validation, configuration, guardrails, persistence, and observability are in place.

---

## Phase 3: User Story 1 – Analyst Triages Alert (Priority: P1) 🎯 MVP

**Goal**: Analysts submit PASS/SUS/FAIL screening results and receive compliant, auditable triage plans with whitelisted actions and summary insights.

**Independent Test**: Using offline fixtures, POST `/triage/plan` should return validated plans for PASS/SUS/FAIL scenarios with correct actions, summary stats, and audit metadata.

### Tests for User Story 1

- [ ] T021 [P] [US1] Create PASS/SUS/FAIL screening fixtures under `backend/src/AML_triage/fixtures/scenarios/` including high-risk corridor variants  
- [ ] T022 [P] [US1] Capture Groq cassette responses & golden plans under `backend/src/AML_triage/fixtures/groq_captures/` and `fixtures/golden_plans/` for offline replay  
- [ ] T023 [P] [US1] Write contract test for `POST /triage/plan` in `backend/tests/AML_triage/contract/test_plan_openapi.py` (schemathesis against OpenAPI)  
- [ ] T024 [P] [US1] Write integration test for SUS scenario in `backend/tests/AML_triage/integration/test_plan_api.py` asserting action whitelist, summary stats, audit fields  

### Implementation for User Story 1

- [ ] T025 [US1] Implement Groq client with httpx retries/offline playback in `backend/src/AML_triage/core/groq_client.py` (configurable `model_id`, `temperature`, strict JSON parsing)  
- [ ] T026 [US1] Define LangGraph state models in `backend/src/AML_triage/agent/state.py` (ingestion payload, validation results, template picks, LLM output, plan draft)  
- [ ] T027 [US1] Implement prompt builder & response schema in `backend/src/AML_triage/agent/prompts.py` injecting action catalogue summaries, template stubs, guardrail reminders  
- [ ] T028 [US1] Implement triage LangGraph in `backend/src/AML_triage/agent/graph.py` orchestrating ingestion → validation → template selection → LLM call → plan validation → guardrail enforcement with max-iteration escape hatch  
- [ ] T029 [US1] Implement plan builder orchestrator in `backend/src/AML_triage/core/plan_builder.py` chaining validation, template stub retrieval, Groq client, JSON schema validation, and summary calculations (action counts, approvals pending, confidence averages)  
- [ ] T030 [US1] Implement FastAPI router factory in `backend/src/AML_triage/api/router.py` exposing `/triage/plan` and `/healthz`, wired to plan builder and config dependencies  
- [ ] T031 [US1] Implement `/healthz` handler returning status, schema_version, strict_fields, offline_mode, templates_loaded, actions_whitelist_size  
- [ ] T032 [US1] Add audit & metrics instrumentation (trace IDs, plan_hash/input_hash, timing, token usage) within plan builder and Groq client  
- [ ] T033 [US1] Implement idempotent adapter stubs (`case_mgmt`, `routing`, `account_controls`, `reg_reporting`) in `backend/src/AML_triage/adapters/*.py` accepting `idempotency_key` and returning mock success  
- [ ] T034 [US1] Add unit tests for plan builder offline execution in `backend/tests/AML_triage/unit/test_plan_builder.py` covering PASS/SUS/FAIL, duplicate detection, guardrail blocking  

**Checkpoint**: `/triage/plan` returns complete plans using offline fixtures; health check and audit logs operational.

---

## Phase 4: User Story 2 – Compliance Review Gates Approvals (Priority: P2)

**Goal**: Compliance reviewers manage approval-required actions, store feedback, and feed signals back into plan generation and few-shot context.

**Independent Test**: When plan includes `PLACE_SOFT_HOLD` or `FILE_STR_DRAFT`, `/triage/plan` marks approvals pending; `/feedback` records reviewer decisions and influences subsequent plan prompts.

### Tests for User Story 2

- [ ] T035 [P] [US2] Write integration test in `backend/tests/AML_triage/integration/test_approvals.py` verifying restricted actions demand approval and approvals update plan state  
- [ ] T036 [P] [US2] Write unit tests for storage persistence & idempotency in `backend/tests/AML_triage/unit/test_storage.py` (plans, approvals, feedback, audit logs)  

### Implementation for User Story 2

- [ ] T037 [US2] Extend `backend/src/AML_triage/core/storage.py` with SQLModel tables for plans, approvals, feedback, plus duplicate submission detection by `input_hash`  
- [ ] T038 [US2] Implement approval workflow utilities in `backend/src/AML_triage/core/approvals.py` (determine approver role, status transitions, audit entry helpers)  
- [ ] T039 [US2] Update plan builder (`core/plan_builder.py`) to populate `approvals_required` block, pending counts, and enforce blocking of unauthorized execution  
- [ ] T040 [US2] Implement `POST /feedback` endpoint in `backend/src/AML_triage/api/router.py` validating labels (`good_pass`, etc.), `action_fit`, and ensuring idempotency  
- [ ] T041 [US2] Implement feedback retrieval service in `backend/src/AML_triage/core/feedback.py` indexing by rule_code set, corridor risk tier, decision for few-shot selection  
- [ ] T042 [US2] Integrate feedback few-shots into prompt builder (`agent/prompts.py`) with clipping to low-token summaries  
- [ ] T043 [US2] Enhance audit logging to capture approval decisions, reviewer hashes, and feedback labels within storage/audit writers  

**Checkpoint**: Approval gating enforced, reviewer feedback stored and reusable, `/feedback` endpoint operational.

---

## Phase 5: User Story 3 – Relationship Manager Communication (Priority: P3)

**Goal**: Plans include compliant communication instructions referencing templated RM briefs and customer document requests tailored to corridor/risk context.

**Independent Test**: For SUS cases requiring outreach, plan output contains `communications` entries with correct template IDs, tone, placeholders, and audit trail includes templates_used.

### Tests for User Story 3

- [ ] T044 [P] [US3] Add unit tests for template retrieval filters in `backend/tests/AML_triage/unit/test_templates.py` (rule triggers, corridor risk, channel)  
- [ ] T045 [P] [US3] Add integration test in `backend/tests/AML_triage/integration/test_comms.py` asserting plans include RM brief & customer doc request instructions with populated placeholders  

### Implementation for User Story 3

- [ ] T046 [US3] Author day-1 action templates under `backend/src/AML_triage/templates/action_templates/*.yaml` (purpose, when_to_use, preconditions, playbook_steps, compliance_notes, fewshot_examples)  
- [ ] T047 [US3] Populate `backend/src/AML_triage/templates/index.json` linking action IDs to template IDs, locales, channels, and version metadata  
- [ ] T048 [US3] Implement retrieval scoring & top-k summarization in `backend/src/AML_triage/core/templates.py`, including corridor/risk/channel filtering and summary strings for prompts  
- [ ] T049 [US3] Update plan builder (`core/plan_builder.py`) to emit `communications` entries with tone (`PROFESSIONAL_INTERNAL`, `NEUTRAL_EXTERNAL`), placeholders, and append `templates_used[]` to audit block  
- [ ] T050 [US3] Implement `comms.send_template` adapter in `backend/src/AML_triage/adapters/comms.py` producing mock rendered messages, masking PII, and recording idempotent calls  

**Checkpoint**: Plans deliver template-driven communications with audit logging of template usage.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, tooling, and integration touchpoints spanning multiple stories.

- [ ] T051 Produce `docs/AML_triage/README.md` runbook detailing assumptions, offline mode, schema/version toggles, and troubleshooting  
- [ ] T052 Add curl script/Postman collection under `docs/AML_triage/api_examples/` covering `/triage/plan`, `/feedback`, `/healthz` demo flows  
- [ ] T053 Create architecture flow slide or diagram (`docs/AML_triage/triage_flow.pptx` or `.drawio`) illustrating LangGraph, validators, adapters, audit pipeline  
- [ ] T054 Expose router mounting helper in `backend/src/AML_triage/api/__init__.py` with example for integrating into parent FastAPI app  
- [ ] T055 Validate Makefile + quickstart by running end-to-end scenario (record findings in `docs/AML_triage/README.md`) and ensure metrics endpoint scraped locally  

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: Setup tasks must precede foundational infrastructure.
- **Phase 2 → User Stories**: Contract registry, validation, config, storage, and metrics are prerequisites for all user stories.
- **User Story Sequence**: US1 (P1) delivers MVP and must complete before US2/US3 to ensure plan builder baseline. US2 and US3 can proceed in parallel once US1 stabilizes, though both depend on plan builder scaffolding.
- **Polish Tasks**: Execute after targeted user stories reach completion; they rely on stable endpoints and fixtures.

---

## Parallel Opportunities

- Within Phase 2, tasks T018–T020 can run concurrently after T010–T017 land.
- During US1, fixture preparation (T021–T022) and test scaffolding (T023–T024) can proceed in parallel.
- US2 integration test (T035) and unit test (T036) can run simultaneously once storage schema exists.
- US3 template authoring (T046–T047) can occur alongside retrieval logic (T048) with close coordination on naming.

---

## Parallel Example: User Story 1

```bash
# Parallel testing setup
Task T021  # Generate PASS/SUS/FAIL fixtures
Task T022  # Capture Groq cassettes and golden plans
Task T023  # Contract test for POST /triage/plan
Task T024  # Integration test for SUS scenario

# After fixtures/tests scaffolded, implement core pipeline
Task T025  # Groq client with offline playback
Task T026  # Agent state models
Task T027  # Prompt builder & schema
Task T028  # LangGraph orchestration
Task T029  # Plan builder orchestrator
Task T030  # FastAPI router factory
```

---

## Implementation Strategy

### MVP First
1. Complete Phases 1–2 to establish contract registry, validation, configuration, storage, and observability.
2. Deliver User Story 1 (T021–T034) to achieve offline plan generation MVP.
3. Demo `/triage/plan` using canned fixtures; validate audit logs and metrics.

### Incremental Delivery
1. Layer User Story 2 (T035–T043) to enable compliance approvals and feedback loops once MVP is stable.
2. Add User Story 3 (T044–T050) to deliver communication outputs and template-driven guidance.
3. Finish with cross-cutting polish (T051–T055) for documentation, demo assets, and integration guidance.

### Team Parallelization
1. Shared effort on Phase 1–2 bootstrap.
2. Assign dedicated owners post-foundation:
   - Developer A: User Story 1 (core pipeline + endpoints)
   - Developer B: User Story 2 (storage, approvals, feedback)
   - Developer C: User Story 3 (templates, communications)
3. Reconvene for Polish tasks and final QA run-through.
