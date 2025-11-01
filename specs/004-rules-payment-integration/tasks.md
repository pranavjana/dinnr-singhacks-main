# Tasks: Rules-Based Payment Analysis Integration

**Input**: Design documents from `/specs/004-rules-payment-integration/`
**Context**: HACKATHON - Prioritizing speed and MVP delivery
**Branch**: `004-rules-payment-integration`

**Organization**: Tasks grouped by user story for independent implementation and rapid iteration.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- File paths are absolute for `/backend` directory

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Minimal project initialization - get to working code fast

**Estimated Time**: 30 minutes

- [X] T001 Create backend project structure: /backend/{agents/aml_monitoring,routers,services,models,core,tests}
- [X] T002 Create requirements.txt with dependencies: fastapi, uvicorn, langgraph, pydantic, supabase, groq, pandas, prometheus-client
- [X] T003 [P] Create .env configuration file in /backend with DATABASE_URL, GROQ_API_KEY, LLM_MODEL
- [X] T004 [P] Create /backend/core/config.py for environment variable loading using pydantic BaseSettings
- [X] T005 [P] Create /backend/core/observability.py with structlog JSON logger and Prometheus metrics setup

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database tables and core infrastructure required by ALL user stories

**Estimated Time**: 45 minutes

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create database migration script /backend/migrations/004_payment_analysis_tables.sql with verdicts, alerts, triggered_rules, detected_patterns, audit_logs tables (see data-model.md)
- [X] T007 Run migration: psql $DATABASE_URL -f /backend/migrations/004_payment_analysis_tables.sql
- [X] T008 [P] Create /backend/models/payment.py with PaymentTransaction Pydantic model (from data-model.md)
- [X] T009 [P] Create /backend/models/verdict.py with Verdict, VerdictType, TeamAssignment Pydantic models
- [X] T010 [P] Create /backend/models/alert.py with Alert, AlertPriority Pydantic models
- [X] T011 [P] Create /backend/models/audit.py with AuditLog Pydantic model (immutable)
- [X] T012 Create /backend/main.py with FastAPI app initialization, CORS, /health endpoint, /metrics endpoint
- [X] T013 [P] Create /backend/services/rules_service.py with RulesService.get_active_rules(jurisdiction) interface to feature 003
- [X] T014 [P] Create /backend/services/history_service.py with HistoryService.get_payment_history(payer_id, beneficiary_id) interface to feature 001

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Real-Time Payment Evaluation (Priority: P1) 🎯 MVP

**Goal**: Submit payment → Receive verdict (pass/suspicious/fail) with team assignment and justification

**Independent Test**: POST payment to /api/v1/payments/analyze → Returns verdict JSON with team assignment

**Estimated Time**: 3-4 hours

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create /backend/agents/aml_monitoring/state_schemas.py with PaymentAnalysisState TypedDict (payment, triggered_rules, detected_patterns, verdict, team, justification, trace_id)
- [ ] T016 [P] [US1] Create /backend/agents/aml_monitoring/rule_checker_agent.py with check_rules_node(state) → queries RulesService, evaluates payment against rules, returns triggered_rules with scores
- [ ] T017 [US1] Create /backend/agents/aml_monitoring/verdict_router.py with calculate_verdict(triggered_rules, detected_patterns) → returns (verdict, team, risk_score, justification) using weighted scoring logic from research.md
- [ ] T018 [US1] Create /backend/agents/aml_monitoring/payment_analysis_agent.py with LangGraph StateGraph: entry → check_rules → assign_verdict → END
- [ ] T019 [US1] Create /backend/services/verdict_service.py with VerdictService.save_verdict(verdict) → inserts to verdicts table, returns verdict_id
- [ ] T020 [US1] Create /backend/services/alert_service.py with AlertService.create_alert(verdict) → inserts to alerts table if verdict != "pass", returns alert_id
- [ ] T021 [US1] Create /backend/routers/payment_analysis.py with POST /api/v1/payments/analyze endpoint → invokes payment_analysis_agent, saves verdict, creates alert if needed, returns AnalysisResult
- [ ] T022 [US1] Add router to /backend/main.py: app.include_router(payment_analysis.router, prefix="/api/v1")
- [ ] T023 [US1] Create audit log writer in /backend/services/audit_service.py with log_analysis(trace_id, payment_id, verdict, reasoning) → inserts to audit_logs table
- [ ] T024 [US1] Add audit logging to payment_analysis_agent.py after verdict assignment

**Checkpoint**: MVP COMPLETE - Can submit payment and get verdict with team routing. Test with curl from quickstart.md

---

## Phase 4: User Story 3 - Team-Based Alert Categorization (Priority: P1)

**Goal**: Automatic team routing (front office/compliance/legal) based on risk type

**Independent Test**: Submit payments with different risk types → Verify correct team assignment

**Estimated Time**: 1 hour

**Note**: This is partially implemented in US1 verdict_router. These tasks enhance it.

### Implementation for User Story 3

- [ ] T025 [US3] Update /backend/agents/aml_monitoring/verdict_router.py with team_routing_logic(triggered_rules, patterns) → deterministic mapping: sanctions/prohibited_jurisdiction → legal, patterns/edd_trigger → compliance, data_quality → front_office
- [ ] T026 [US3] Add investigation_steps generation in verdict_router.py based on team assignment (e.g., compliance → "Review transaction frequency", legal → "Check sanctions database")
- [ ] T027 [US3] Update AlertService.create_alert() to include investigation_steps field from verdict
- [ ] T028 [US3] Create GET /api/v1/alerts endpoint in /backend/routers/alerts.py with filters: assigned_team, priority, status
- [ ] T029 [US3] Create PATCH /api/v1/alerts/{alert_id} endpoint for status updates (pending → under_review → resolved)
- [ ] T030 [US3] Add alerts router to main.py: app.include_router(alerts.router, prefix="/api/v1")

**Checkpoint**: Team routing validated - Alerts automatically categorized and queryable by team

---

## Phase 5: User Story 2 - Pattern Recognition (Priority: P2)

**Goal**: Detect money laundering patterns (structuring, velocity, jurisdictional, etc.) in payment history

**Independent Test**: Submit payment from account with suspicious history → Pattern detected in verdict

**Estimated Time**: 2-3 hours

### Implementation for User Story 2

- [ ] T031 [P] [US2] Create /backend/agents/aml_monitoring/pattern_detector_agent.py with detect_patterns_node(state) → calls HistoryService, runs pattern detection functions, returns detected_patterns list
- [ ] T032 [P] [US2] Implement detect_structuring(payment, history) in pattern_detector_agent.py → checks for multiple transactions <$10K in 24h window summing >$10K
- [ ] T033 [P] [US2] Implement detect_velocity(payment, history) in pattern_detector_agent.py → calculates z-score vs 90-day baseline, flags if >5σ
- [ ] T034 [P] [US2] Implement detect_jurisdictional_risk(payment, history) in pattern_detector_agent.py → checks for high concentration in FATF blacklist countries
- [ ] T035 [P] [US2] Implement detect_round_tripping(payment, history) in pattern_detector_agent.py → looks for circular flows A→B→C→A within 7 days
- [ ] T036 [P] [US2] Implement detect_layering(payment, history) in pattern_detector_agent.py → detects complex multi-hop transactions
- [ ] T037 [US2] Create /backend/models/pattern.py with DetectedPattern, PatternType Pydantic models
- [ ] T038 [US2] Create /backend/services/pattern_service.py with save_detected_pattern(pattern) → inserts to detected_patterns table
- [ ] T039 [US2] Update /backend/agents/aml_monitoring/payment_analysis_agent.py to add detect_patterns node in parallel with check_rules (both feed into assign_verdict)
- [ ] T040 [US2] Update verdict_router.py calculate_verdict() to include pattern_score in risk calculation (rule_score + pattern_score → total_score)
- [ ] T041 [US2] Update routers/payment_analysis.py to save detected patterns via PatternService after analysis

**Checkpoint**: Pattern detection working - Verdicts now consider both rules AND historical patterns

---

## Phase 6: User Story 4 - Report Generation (Priority: P2)

**Goal**: Generate comprehensive reports with verdicts, rules, patterns, recommendations

**Independent Test**: GET /api/v1/reports/payment/{id} → Returns detailed analysis report

**Estimated Time**: 1-2 hours

### Implementation for User Story 4

- [ ] T042 [P] [US4] Create /backend/models/report.py with PaymentReport, AggregateReport Pydantic models
- [ ] T043 [US4] Create /backend/services/report_service.py with generate_payment_report(payment_id) → queries verdicts, triggered_rules, detected_patterns, formats as PaymentReport
- [ ] T044 [US4] Implement generate_aggregate_report(start_date, end_date) in report_service.py → queries verdicts table, aggregates by verdict/team/pattern type
- [ ] T045 [US4] Create /backend/routers/reports.py with GET /api/v1/reports/payment/{payment_id} endpoint
- [ ] T046 [US4] Add GET /api/v1/reports/aggregate endpoint with start_date, end_date query params
- [ ] T047 [US4] Add reports router to main.py: app.include_router(reports.router, prefix="/api/v1")

**Checkpoint**: Reporting complete - Can generate individual and aggregate analysis reports

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Performance, observability, and hackathon demo readiness

**Estimated Time**: 1-2 hours

- [ ] T048 [P] Add Prometheus metrics to payment_analysis.py: aml_payment_analysis_total counter, aml_analysis_latency_ms histogram
- [ ] T049 [P] Add structured logging with trace_id to all agent nodes in payment_analysis_agent.py
- [ ] T050 [P] Implement circuit breaker in /backend/core/circuit_breaker.py for Groq API calls (3 retries, 5s timeout, exponential backoff)
- [ ] T051 Add error handling for missing rules/history data in rule_checker and pattern_detector agents (graceful degradation)
- [ ] T052 [P] Create /backend/routers/verdicts.py with GET /api/v1/verdicts/{verdict_id} and GET /api/v1/verdicts (query endpoint)
- [ ] T053 Add verdicts router to main.py
- [ ] T054 [P] Update quickstart.md with example curl commands for all implemented endpoints
- [ ] T055 Test full workflow: payment submission → verdict with patterns → alert creation → report generation (validate against quickstart.md)
- [ ] T056 [P] Add OpenAPI schema generation to main.py (FastAPI auto-generates from Pydantic models)
- [ ] T057 Create demo script /backend/demo.py with 3 example payments (pass, suspicious, fail scenarios) for hackathon presentation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - Start immediately ✅
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories ⚠️
- **User Stories (Phase 3-6)**: All depend on Foundational phase
  - **US1 (P1)**: Can start immediately after Foundational - MVP target 🎯
  - **US3 (P1)**: Builds on US1 verdict router - Quick enhancement
  - **US2 (P2)**: Enhances US1 with patterns - Independent feature
  - **US4 (P2)**: Queries US1/US2 results - Independent feature
- **Polish (Phase 7)**: Can run in parallel with user stories or after

### HACKATHON MVP STRATEGY 🚀

**For fastest demo** (3-4 hours):
1. Complete Phase 1 (Setup) - 30 min
2. Complete Phase 2 (Foundational) - 45 min
3. Complete Phase 3 (US1) - 3-4 hours
4. **STOP**: You now have a working MVP! Can analyze payments and get verdicts.
5. Demo with curl from quickstart.md

**If time allows** (additional 2-3 hours):
6. Add Phase 4 (US3 team routing enhancements) - 1 hour
7. Add Phase 5 (US2 pattern detection) - 2-3 hours
8. **STOP**: Full feature set except reporting

**If even more time** (additional 1-2 hours):
9. Add Phase 6 (US4 reporting) - 1-2 hours
10. Add Phase 7 (polish) - 1-2 hours

### User Story Dependencies

- **US1 (Real-Time Evaluation)**: No dependencies - START HERE for MVP ✅
- **US3 (Team Routing)**: Builds on US1 verdict_router - Quick win
- **US2 (Pattern Detection)**: Independent of US1/US3 - Can develop in parallel
- **US4 (Reporting)**: Depends on US1/US2/US3 data existing - Do last

### Within Each User Story

- Models can be created in parallel [P]
- Services depend on models
- Agents depend on services
- Routers depend on agents
- Always integrate with main.py after router creation

### Parallel Opportunities

**Setup (Phase 1)**: All [P] tasks can run together
- T003 (.env), T004 (config.py), T005 (observability.py)

**Foundational (Phase 2)**: All models can run in parallel
- T008 (payment.py), T009 (verdict.py), T010 (alert.py), T011 (audit.py)
- T013 (rules_service.py), T014 (history_service.py)

**US1**: Models in parallel
- T015 (state_schemas.py), T016 (rule_checker_agent.py) can start together

**US2**: All pattern detection functions in parallel
- T032 (structuring), T033 (velocity), T034 (jurisdictional), T035 (round_tripping), T036 (layering)

**US4**: Both report functions in parallel
- T042 (report.py model), T043 (payment report), T044 (aggregate report)

**Polish**: Most tasks are independent
- T048 (metrics), T049 (logging), T050 (circuit breaker), T054 (docs), T056 (OpenAPI), T057 (demo)

---

## Parallel Example: User Story 1 (MVP)

```bash
# After Foundational phase completes, launch US1 tasks in batches:

# Batch 1 - Models and schemas (parallel):
Task T015: "Create state_schemas.py"
Task T016: "Create rule_checker_agent.py"

# Batch 2 - Agent logic (sequential, depends on Batch 1):
Task T017: "Create verdict_router.py"
Task T018: "Create payment_analysis_agent.py"

# Batch 3 - Services (parallel, depends on Batch 2):
Task T019: "Create verdict_service.py"
Task T020: "Create alert_service.py"
Task T023: "Create audit_service.py"

# Batch 4 - API (sequential, depends on Batch 3):
Task T021: "Create payment_analysis.py router"
Task T022: "Add router to main.py"
Task T024: "Add audit logging"

# Result: MVP complete in ~3-4 hours
```

---

## Parallel Example: User Story 2 (Pattern Detection)

```bash
# All pattern detection functions can run in parallel:

Task T032: "Implement detect_structuring()"
Task T033: "Implement detect_velocity()"
Task T034: "Implement detect_jurisdictional_risk()"
Task T035: "Implement detect_round_tripping()"
Task T036: "Implement detect_layering()"

# Result: 5 patterns implemented simultaneously by 5 developers or sequentially by 1
```

---

## Implementation Strategy

### Hackathon MVP First (US1 Only) - RECOMMENDED 🎯

**Target**: Working payment analysis in 4-5 hours

1. ✅ Complete Phase 1: Setup (30 min)
2. ✅ Complete Phase 2: Foundational (45 min)
3. ✅ Complete Phase 3: User Story 1 (3-4 hours)
4. **STOP and VALIDATE**:
   - Run: `uvicorn main:app --reload`
   - Test: `curl -X POST http://localhost:8000/api/v1/payments/analyze -H "Content-Type: application/json" -d @test_payment.json`
   - Verify: Receive verdict JSON with team assignment
5. **DEMO READY**: You can present payment analysis with verdict assignment

**Hackathon Pitch**: "Our system analyzes payments in real-time, assigns risk verdicts (pass/suspicious/fail), and automatically routes alerts to the right team (front office, compliance, legal). Watch as I submit this payment..." [run curl command, show JSON response]

### Incremental Delivery (If Time Allows)

**After MVP (US1)**:

1. Add User Story 3 (team routing enhancements) - 1 hour → Demo: "Now we have alert management endpoints"
2. Add User Story 2 (pattern detection) - 2-3 hours → Demo: "System now detects 5 types of money laundering patterns"
3. Add User Story 4 (reporting) - 1-2 hours → Demo: "Generate comprehensive audit reports"
4. Add Polish - 1-2 hours → Demo: "Production-ready with metrics and observability"

### Parallel Team Strategy (If Multiple Developers)

**With 2 developers**:
1. Both: Complete Setup + Foundational together (1.5 hours)
2. Split:
   - Developer A: User Story 1 (MVP core) - 3-4 hours
   - Developer B: User Story 2 (pattern detection) - 2-3 hours
3. Developer A finishes first → Add US3 team routing (1 hour)
4. Both: Integrate and test (30 min)
5. Developer B: Add US4 reporting while A does polish

**Result**: 5-6 hours to complete all user stories vs 8-10 hours solo

---

## Task Count Summary

- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 9 tasks
- **Phase 3 (US1 - MVP)**: 10 tasks ← START HERE
- **Phase 4 (US3 - Team Routing)**: 6 tasks
- **Phase 5 (US2 - Patterns)**: 11 tasks
- **Phase 6 (US4 - Reports)**: 6 tasks
- **Phase 7 (Polish)**: 10 tasks

**Total**: 57 tasks

**MVP Only**: 24 tasks (Phase 1 + 2 + 3)
**Core Features**: 41 tasks (MVP + US3 + US2)
**Complete**: 57 tasks (all phases)

---

## Notes

- [P] = Can run in parallel (different files, no blocking dependencies)
- [Story] = Maps to user story for traceability (US1, US2, US3, US4)
- File paths are absolute for `/backend` directory
- Commit after each task or logical group
- Each user story checkpoint = shippable increment
- For hackathon: FOCUS ON US1 MVP FIRST, then expand if time allows
- Avoid: premature optimization, over-engineering, complex testing (get it working first)
- Demo priority: US1 (verdict assignment) > US2 (pattern detection) > US3 (team routing) > US4 (reporting)
