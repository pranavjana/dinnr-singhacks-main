# Research Log — Post-Screening AML Triage Layer

## Decision: Adopt Python 3.11 with FastAPI, Pydantic v2, and LangGraph for the triage service
- **Rationale**: Aligns with the existing backend stack, delivers async-friendly performance, and satisfies the constitution’s agentic AI requirement via LangGraph’s typed state management. Python 3.11 offers perf gains and broad library support.
- **Alternatives considered**: Python 3.10 (would miss perf/runtime improvements), Node.js + NestJS (deviates from constitution’s LangGraph mandate and existing tooling).

## Decision: Integrate Groq chat completions (llama-3.3-70b-versatile primary, 3.1-8b-instant fallback) with recorded-response offline mode
- **Rationale**: Matches feature scope, provides deterministic JSON-mode completions, and honours offline constraint by allowing cassette playback from fixtures when `OFFLINE_MODE=true`.
- **Alternatives considered**: OpenAI GPT-4o (no offline path, higher cost), local LLM (insufficient quality for compliance reasoning).

## Decision: Implement a contract registry backed by JSON Schema files plus alias resolution
- **Rationale**: Enables versioned ScreeningResult evolution, strict validation, and controlled alias mapping through `contracts/screening_result.v1.json` and `aliases.yaml`.
- **Alternatives considered**: Hard-coded Pydantic models (rigid, high change cost), dynamic schema inference (non-deterministic, violates policy guardrails).

## Decision: Persist plans, approvals, and feedback in local SQLite with append-only JSON audit logs
- **Rationale**: Satisfies hackathon offline demo constraint, provides transactional integrity for feedback retrieval, and supports immutable logging for compliance review.
- **Alternatives considered**: In-memory storage (no durability), external managed DB (breaks offline requirement).

## Decision: Use structlog + Prometheus client for observability and audit pipeline
- **Rationale**: Enables structured, PII-safe logs with hashed identifiers and per-stage metrics (validation, LLM, policy checks) to meet constitution monitoring demands.
- **Alternatives considered**: Standard logging (less structured, harder to enforce masking), custom metric solution (longer to implement, less tooling support).

## Decision: Represent action catalogue and template library as YAML/JSON assets with loader services
- **Rationale**: Simplifies updates by compliance teams, keeps tokens low for prompts, and enforces approval metadata centrally.
- **Alternatives considered**: Database-stored catalogue (overkill for hackathon), embedding templates directly in prompts (hard to version/audit).
