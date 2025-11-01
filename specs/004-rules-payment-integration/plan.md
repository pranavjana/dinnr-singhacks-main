# Implementation Plan: Rules-Based Payment Analysis Integration

**Branch**: `004-rules-payment-integration` | **Date**: 2025-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-rules-payment-integration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Integrate AML rules extraction (feature 003) with payment history analysis (feature 001) to provide comprehensive, real-time risk assessment of payment transactions. The system will analyze each payment against both regulatory rules and historical patterns, assign verdicts (pass/suspicious/fail), route alerts to appropriate teams (front office/compliance/legal), and generate audit-ready reports with pattern detection and investigation recommendations.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.100+, LangGraph 0.1+, Pydantic (schema validation), Groq API with Kimi K2-0905 model, pandas (transaction analysis)
**Storage**: Supabase PostgreSQL (transaction history, AML rules, verdicts, alerts, audit logs)
**Testing**: pytest (backend unit/integration), contract tests for API endpoints
**Target Platform**: Linux server (Docker containerized)
**Project Type**: Web application (backend API component)
**Performance Goals**: <500ms transaction analysis latency (p95), <1000ms alert generation, 100 concurrent requests without degradation
**Constraints**: <30 seconds total analysis time per payment (rule + pattern analysis), audit trail immutability, real-time alert delivery
**Scale/Scope**: 1000+ payments/day analysis capacity, pattern detection across 10K+ historical transactions per entity, support for 3 team roles (front office/compliance/legal), 5+ money laundering pattern types

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Agentic AI-First Architecture ✅
- **Requirement**: Workflows implemented as stateful LangGraph agents with memory and audit trails
- **Compliance**: Payment analysis will be a LangGraph workflow integrating rule-checking and pattern-detection sub-agents
- **Implementation**: StateGraph with typed Pydantic state, conditional routing for verdict assignment, logged reasoning chains

### Principle II: Real-Time Monitoring & Alerting ✅
- **Requirement**: Sub-second alert generation, role-specific routing, actionable remediation
- **Compliance**: <500ms analysis latency, automatic team assignment (front/compliance/legal), investigation recommendations in reports
- **Implementation**: FastAPI async endpoints, priority-based alert queue, team-routing logic in LangGraph conditional edges

### Principle III: Audit Trail & Compliance First ✅
- **Requirement**: Immutable logs with timestamp, user, rationale, regulatory reference
- **Compliance**: All verdicts logged with triggered rules, detected patterns, team assignment, and justification
- **Implementation**: Supabase audit table with append-only constraint, structured JSON logging for all agent decisions

### Principle IV: Multi-Format Document Handling ⚠️ N/A (Future)
- **Requirement**: PDF/image processing, OCR, authenticity verification
- **Status**: Not applicable to this feature (payment transaction analysis only; no document corroboration)
- **Note**: Feature 002 (pdf-document-processing) handles document analysis

### Principle V: Security & Data Minimization ✅
- **Requirement**: Encryption at rest/transit, RBAC, no PII logging, data retention policies
- **Compliance**: Supabase AES-256 encryption, TLS 1.3+ for Groq API, role-based alert access, no raw account numbers in logs
- **Implementation**: Environment-based secrets, hashed identifiers in audit logs, configurable data retention per jurisdiction

### Principle VI: Scalable, Observable Backend ✅
- **Requirement**: Prometheus metrics, JSON logs, request tracing, <500ms analysis SLA
- **Compliance**: Metrics for transactions analyzed, alerts generated, pattern types detected; trace_id propagation
- **Implementation**: `/metrics` endpoint, structured logging with trace_id, Langsmith agent observability, circuit breakers for Groq API

### Principle VII: Backend Organization & Folder Structure ✅
- **Requirement**: All backend code in `/backend` directory
- **Compliance**: Feature implementation entirely in `/backend/agents/aml_monitoring/`, `/backend/routers/`, `/backend/services/`
- **Implementation**: No frontend code in this feature; API contracts define REST endpoints for future frontend integration

### Principle VIII: Frontend UX for Compliance Officers ⚠️ N/A (Future)
- **Requirement**: Next.js dashboards, role-specific views, ≤3 clicks workflows
- **Status**: Backend-only feature; frontend integration deferred to separate feature
- **Note**: API contracts prepared for frontend consumption with risk-level color coding standards documented

### Constitutional Gates Status

| Gate | Status | Notes |
|------|--------|-------|
| Agentic AI-First | ✅ PASS | LangGraph workflow with state, memory, audit trails |
| Real-Time Alerts | ✅ PASS | <500ms latency, role routing, remediation suggestions |
| Audit Trail | ✅ PASS | Immutable logs, structured reasoning chains |
| Document Handling | ⚠️ DEFERRED | N/A for payment analysis (feature 002 scope) |
| Security | ✅ PASS | Encryption, RBAC, no PII leakage |
| Observability | ✅ PASS | Metrics, logs, tracing, SLA compliance |
| Backend Folder Structure | ✅ PASS | All code in `/backend` directory |
| Frontend UX | ⚠️ DEFERRED | Backend-only; API contracts ready for future frontend |

**Overall Status**: ✅ **PASS** - All applicable constitutional requirements satisfied; deferred items are out-of-scope for backend-focused feature

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── agents/
│   └── aml_monitoring/
│       ├── payment_analysis_agent.py      # Main LangGraph workflow
│       ├── rule_checker_agent.py          # Sub-agent for rule evaluation
│       ├── pattern_detector_agent.py      # Sub-agent for pattern recognition
│       ├── verdict_router.py              # Conditional logic for verdict/team assignment
│       └── state_schemas.py               # Pydantic state definitions
├── routers/
│   └── payment_analysis.py                # FastAPI endpoints for payment submission
├── services/
│   ├── rules_service.py                   # Interface to feature 003 (rule extraction)
│   ├── history_service.py                 # Interface to feature 001 (payment history)
│   ├── verdict_service.py                 # Verdict persistence and retrieval
│   └── alert_service.py                   # Alert generation and team routing
├── models/
│   ├── payment.py                         # Payment transaction schema
│   ├── verdict.py                         # Verdict model
│   ├── alert.py                           # Alert model
│   └── audit.py                           # Audit log schema
├── core/
│   ├── config.py                          # Environment-based configuration
│   └── observability.py                   # Metrics, logging, tracing utilities
└── tests/
    ├── unit/
    │   ├── test_rule_checker.py
    │   ├── test_pattern_detector.py
    │   └── test_verdict_router.py
    ├── integration/
    │   ├── test_payment_analysis_agent.py
    │   └── test_api_endpoints.py
    └── contract/
        └── test_api_contracts.py

Database (Supabase PostgreSQL):
├── tables/
│   ├── payments                           # Transaction records
│   ├── aml_rules                          # Extracted rules (from feature 003)
│   ├── payment_history                    # Historical transactions (from feature 001)
│   ├── verdicts                           # Analysis results
│   ├── alerts                             # Flagged payments
│   └── audit_logs                         # Immutable decision log
```

**Structure Decision**: Web application backend component within `/backend` directory per Constitution Principle VII. This feature is backend-only (LangGraph agents + FastAPI API). Frontend integration deferred to future feature. Agent workflows organized under `/backend/agents/aml_monitoring/` following agentic AI-first principle.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitutional violations detected. All applicable principles satisfied.

## Phase 0: Research (Completed)

**Artifacts Generated**:
- ✅ `research.md`: All technical unknowns resolved
  - LangGraph multi-agent orchestration pattern selected (coordinator + sub-agents)
  - Integration strategy with features 001 & 003 defined (service layer abstraction)
  - Verdict assignment logic specified (weighted scoring + deterministic team routing)
  - Pattern detection strategies documented (5 core patterns: structuring, velocity, jurisdictional, round-tripping, layering)
  - Performance optimization approach defined (async FastAPI, parallel agents, database indexing)
  - Audit trail & observability architecture specified (Prometheus, Langsmith, structured JSON logs)
  - Error handling strategies documented (circuit breakers, graceful degradation)

**Key Decisions**:
- Multi-agent LangGraph workflow with parallel rule checking and pattern detection
- Service layer for loose coupling with dependency features
- Deterministic verdict logic for auditability (vs LLM-based)
- Rule-based pattern detectors (vs ML models) for determinism and speed

## Phase 1: Design & Contracts (Completed)

**Artifacts Generated**:
- ✅ `data-model.md`: Complete entity definitions with Pydantic models and SQL schemas
  - 6 core entities: PaymentTransaction, Verdict, Alert, TriggeredRule, DetectedPattern, AuditLog
  - Database schema with indexes for <50ms query latency
  - Validation rules ensuring data integrity
  - State transition diagrams for verdict and alert lifecycles

- ✅ `contracts/openapi.yaml`: REST API specification (OpenAPI 3.1)
  - 9 endpoints covering analysis, verdicts, alerts, reports, health
  - Request/response schemas with validation
  - Error responses and status codes
  - Example requests for pass/suspicious/fail scenarios

- ✅ `quickstart.md`: Developer onboarding guide
  - 5-minute quick start with environment setup
  - Database migration scripts
  - Test commands and expected outputs
  - Troubleshooting guide
  - Observability setup (metrics, logs, tracing)

**Agent Context Updated**: ✅
- Added Python 3.11+ stack to CLAUDE.md
- Added FastAPI, LangGraph, Groq Kimi K2, Pydantic, pandas
- Added Supabase PostgreSQL dependency

## Post-Design Constitution Re-Evaluation

### Constitutional Gates Status (Re-check)

| Gate | Pre-Design | Post-Design | Notes |
|------|------------|-------------|-------|
| Agentic AI-First | ✅ PASS | ✅ PASS | LangGraph workflow fully designed (see data-model.md for state schemas) |
| Real-Time Alerts | ✅ PASS | ✅ PASS | API contracts confirm <500ms latency, team routing endpoints defined |
| Audit Trail | ✅ PASS | ✅ PASS | Audit logs table with append-only constraint (see data-model.md) |
| Document Handling | ⚠️ DEFERRED | ⚠️ DEFERRED | Out of scope (feature 002 handles documents) |
| Security | ✅ PASS | ✅ PASS | Environment-based secrets, no PII in logs, encrypted storage |
| Observability | ✅ PASS | ✅ PASS | Prometheus metrics endpoint, Langsmith tracing, structured logs |
| Backend Folder Structure | ✅ PASS | ✅ PASS | All code in `/backend/agents/aml_monitoring`, `/backend/routers`, `/backend/services` |
| Frontend UX | ⚠️ DEFERRED | ⚠️ DEFERRED | API contracts ready for future frontend (see openapi.yaml) |

**Overall Status**: ✅ **PASS** - All applicable constitutional requirements satisfied post-design.

### Design Validation Checklist

- [x] LangGraph agents use typed Pydantic state schemas (`PaymentAnalysisState` in research.md)
- [x] All database tables have foreign key constraints and indexes
- [x] API contracts follow RESTful conventions (GET/POST/PATCH with proper resources)
- [x] Error responses include trace_id for debugging
- [x] Audit logs are immutable (database rules prevent UPDATE/DELETE)
- [x] Metrics exposed at `/metrics` endpoint (Prometheus format)
- [x] All code artifacts documented in `/backend` directory structure
- [x] No implementation details leaked into specification (spec.md remains technology-agnostic)

## Summary

**Feature**: Rules-Based Payment Analysis Integration (004-rules-payment-integration)

**Objective**: Integrate AML rules extraction (feature 003) and payment history analysis (feature 001) to provide real-time payment risk assessment with verdict assignment (pass/suspicious/fail), team routing (front office/compliance/legal), pattern detection, and audit-ready reporting.

**Architecture**: LangGraph multi-agent workflow with FastAPI backend, Supabase PostgreSQL storage, Groq Kimi K2 LLM for reasoning.

**Key Features**:
- Real-time payment analysis (<500ms p95 latency)
- 3-tier verdict system (pass/suspicious/fail)
- Automated team routing (front office/compliance/legal)
- 5 pattern types detected (structuring, velocity, jurisdictional, round-tripping, layering)
- Comprehensive audit trail (immutable logs)
- REST API for frontend integration

**Planning Status**: ✅ **COMPLETE**
- Phase 0 (Research): Complete
- Phase 1 (Design & Contracts): Complete
- Constitutional compliance: Validated pre- and post-design

**Next Phase**: `/speckit.tasks` - Generate implementation task breakdown

**Estimated Implementation**: 3-4 days for 2 backend engineers
- Day 1: LangGraph agent workflows + state schemas
- Day 2: FastAPI endpoints + service layer integration
- Day 3: Database persistence + pattern detection logic
- Day 4: Testing, observability, deployment

**Ready for**: Task generation (`/speckit.tasks`)
