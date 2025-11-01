# Implementation Plan: Post-Screening AML Triage Layer

**Branch**: `feature/004-post-screening-aml-triage` | **Date**: 2025-11-01 | **Spec**: specs/004-post-screening-aml-triage/spec.md  
**Input**: Feature specification from `/specs/004-post-screening-aml-triage/spec.md`

## Summary

Build an offline-capable AML triage microservice that converts screening decisions into policy-compliant action plans by orchestrating a LangGraph-driven agent, Groq LLM completions under JSON schema rails, a contract registry for ScreeningResult evolution, and a versioned template/action catalogue guarded by deterministic validators and audit logging.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI stack)  
**Primary Dependencies**: FastAPI, Pydantic v2, LangGraph, httpx, orjson, structlog, SQLModel/SQLite, pytest, respx for HTTP mocks, groq-sdk  
**Storage**: Local SQLite (plans, approvals, feedback), append-only JSON audit logs on disk  
**Testing**: pytest with pytest-asyncio, pytest-httpx/respx, schemathesis for contract checks  
**Target Platform**: Linux container / macOS dev host, deployable as FastAPI ASGI app  
**Project Type**: Backend agentic service (single FastAPI project)  
**Performance Goals**: <500 ms validation + routing; <2 s end-to-end plan generation with cached templates; health check p95 <50 ms  
**Constraints**: Offline-friendly via recorded Groq fixtures; idempotent tool adapters; LangGraph max 10 iterations; strict JSON schema validation; PII hashing/masking  
**Scale/Scope**: Support ≥50 canned scenarios per corridor during demo; concurrency target 25 rps on single worker; maintain action catalogue ≤100 entries

## Constitution Check

- **Principle I — Agentic AI-First Architecture**: PASS. Design centers on a LangGraph workflow with typed state (`TriageState`), explicit nodes for ingestion, validation, LLM planning, policy vetting, and action commits. Iteration cap + audit trail preserved.  
- **Principle II — Real-Time Monitoring & Alerting**: PASS. Prometheus metrics for latency, queue depth, and risk counts; structured logs feed alerting.  
- **Principle III — Audit Trail & Compliance**: PASS. Plan storage + immutable JSON logs include hashes, rationale, approvals, reviewer IDs.  
- **Principle V — Security & Data Minimization**: PASS. Hash identifiers, mask accounts, secrets via env, no raw PII in prompts.  
- **Principle VI — Scalable, Observable Backend**: PASS. FastAPI app exposes `/healthz`, metrics middleware, tracing IDs; Groq integration wrapped with circuit breakers.  
- **Re-check after design**: All gates remain satisfied with detailed data model, contracts, and offline fallback plans documented below.

## Project Structure

### Documentation (this feature)

```text
specs/004-post-screening-aml-triage/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md          # generated in Phase 2
```

### Source Code (repository root)

```text
backend/
├── src/
│   └── AML_triage/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py          # FastAPI router mounting endpoints
│       │   └── dependencies.py    # auth/context providers
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py          # settings, Groq creds, offline toggles
│       │   ├── contracts.py       # contract registry loader + alias resolver
│       │   ├── validation.py      # JSON schema + policy checks
│       │   ├── templates.py       # template retrieval and filtering
│       │   ├── actions.py         # action catalogue loading/enforcement
│       │   ├── storage.py         # SQLite + JSON log writers
│       │   └── metrics.py         # observability helpers
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── graph.py           # LangGraph definition for triage flow
│       │   ├── state.py           # Pydantic state models
│       │   └── prompts.py         # Groq prompt builders + schema
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── case_mgmt.py
│       │   ├── routing.py
│       │   ├── account_controls.py
│       │   ├── reg_reporting.py
│       │   └── comms.py
│       ├── fixtures/
│       │   ├── __init__.py
│       │   ├── scenarios/         # PASS/SUS/FAIL demo payloads
│       │   └── groq_captures/     # recorded responses for offline mode
│       ├── templates/
│       │   ├── action_catalogue.json
│       │   ├── index.json
│       │   └── action_templates/
│       └── contracts/
│           ├── screening_result.v1.json
│           ├── aliases.yaml
│           └── migrations/
└── tests/
    └── AML_triage/
        ├── unit/
        │   ├── test_contracts.py
        │   ├── test_templates.py
        │   ├── test_validator.py
        │   └── test_agent_graph.py
        ├── integration/
        │   ├── test_plan_api.py
        │   ├── test_feedback_api.py
        │   └── test_offline_mode.py
        └── contract/
            └── test_openapi.py
```

**Structure Decision**: Single FastAPI backend module under `backend/src/AML_triage` with LangGraph-centric `agent/` package, explicit `core/` services for configuration/validation, adapter stubs for idempotent actions, and mirrored test hierarchy in `backend/tests/AML_triage` for unit, integration, and contract coverage.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | — | — |
