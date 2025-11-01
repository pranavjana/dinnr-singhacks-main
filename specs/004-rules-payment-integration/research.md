# Research & Technical Decisions: Rules-Based Payment Analysis Integration

**Feature**: 004-rules-payment-integration
**Date**: 2025-11-01
**Status**: Completed

## Purpose

This document consolidates research findings and technical decisions for integrating AML rules extraction (feature 003) with payment history analysis (feature 001) to create a comprehensive, real-time payment risk assessment system.

## Research Areas

### 1. LangGraph Multi-Agent Orchestration Patterns

**Decision**: Use hierarchical StateGraph with coordinator agent and specialized sub-agents

**Rationale**:
- **Coordinator Pattern**: Main `PaymentAnalysisAgent` orchestrates two parallel sub-agents (rule checker, pattern detector) and a verdict router
- **State Management**: Shared Pydantic state passed between nodes ensures type safety and auditability
- **Parallel Execution**: Rule checking and pattern detection can run concurrently for <500ms latency target
- **Conditional Routing**: Verdict router uses conditional edges to assign team based on triggered rules/patterns

**Alternatives Considered**:
1. **Sequential Pipeline**: Rule check → Pattern detection → Verdict assignment (rejected: slower, doesn't meet latency SLA)
2. **Single Monolithic Agent**: One LLM call for all analysis (rejected: less modular, harder to debug, opaque reasoning)
3. **Event-Driven Microservices**: Separate services for rules/patterns with message queue (rejected: over-engineered for hackathon, higher latency)

**Implementation Pattern**:
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal

class PaymentAnalysisState(TypedDict):
    payment: dict
    historical_transactions: list[dict]
    triggered_rules: list[dict]
    detected_patterns: list[dict]
    verdict: Literal["pass", "suspicious", "fail"]
    assigned_team: Literal["front_office", "compliance", "legal"]
    justification: str
    trace_id: str

workflow = StateGraph(PaymentAnalysisState)

# Add nodes
workflow.add_node("check_rules", rule_checker_node)
workflow.add_node("detect_patterns", pattern_detector_node)
workflow.add_node("assign_verdict", verdict_router_node)
workflow.add_node("generate_alert", alert_generator_node)

# Define edges with conditional routing
workflow.set_entry_point("check_rules")
workflow.add_edge("check_rules", "detect_patterns")
workflow.add_edge("detect_patterns", "assign_verdict")
workflow.add_conditional_edges(
    "assign_verdict",
    lambda state: "alert" if state["verdict"] != "pass" else "end",
    {"alert": "generate_alert", "end": END}
)
workflow.add_edge("generate_alert", END)
```

**Best Practices Applied**:
- Max iterations set to 3 (escape hatch for loops)
- All state transitions logged with timestamp and reasoning
- Sub-agents return confidence scores for verdict weighting
- Circuit breaker on Groq API calls (3 retries, 5s timeout)

### 2. Integration with Existing Features

**Decision**: Service layer abstraction for features 001 and 003

**Rationale**:
- **Loose Coupling**: `RulesService` and `HistoryService` provide clean interfaces to dependency features
- **Graceful Degradation**: If feature 003 rules not available, fall back to rule-free pattern analysis
- **Database Access**: Both features use Supabase PostgreSQL; services query `compliance_rules` and `payment_history` tables directly
- **Data Contracts**: Clearly defined schemas ensure compatibility (feature 003 provides `ComplianceRule` model, feature 001 provides transaction list)

**Feature 001 Integration (Payment History Analysis)**:
- **Interface**: `HistoryService.get_payment_history(payer_id, beneficiary_id) -> List[Transaction]`
- **Data Source**: Query `payment_history` table with OR logic (payer OR beneficiary match)
- **Output**: List of historical transactions with all fields (amount, jurisdiction, date, screening flags)
- **Deduplication**: Feature 001 already handles transaction_id deduplication per spec

**Feature 003 Integration (Rule Extraction)**:
- **Interface**: `RulesService.get_active_rules(jurisdiction, regulator) -> List[ComplianceRule]`
- **Data Source**: Query `compliance_rules` table filtered by `is_active=true`, `validation_status='validated'`
- **Output**: Structured rules with `rule_type`, `rule_data` (JSONB), `effective_date`, `jurisdiction`
- **Versioning**: Service automatically filters for current effective rules (no expired/superseded rules)

**Alternatives Considered**:
1. **Direct Database Access**: Skip service layer, query tables directly in agent nodes (rejected: tight coupling, harder to test)
2. **API Gateway**: Create REST API wrapper around features 001/003 (rejected: unnecessary latency overhead)
3. **Event Bus**: Publish payment event, subscribe to rule/pattern services (rejected: async complexity for real-time use case)

### 3. Verdict Assignment Logic

**Decision**: Multi-factor weighted scoring with deterministic team routing

**Rationale**:
- **Verdict Calculation**: Combine rule severity scores + pattern confidence scores → threshold-based verdict
  - `pass`: Total risk score < 30
  - `suspicious`: 30 ≤ risk score < 70
  - `fail`: Risk score ≥ 70
- **Team Routing**: Deterministic logic based on highest-severity trigger type
  - **Front Office**: Operational issues (missing fields, data quality, formatting errors)
  - **Compliance**: Pattern-based alerts (structuring, velocity, unusual behavior)
  - **Legal**: Explicit rule violations (sanctions, prohibited jurisdictions, regulatory thresholds)
- **Tie-Breaking**: If multiple high-severity triggers, escalate to legal team (most stringent review)

**Alternatives Considered**:
1. **LLM-Based Verdict**: Let Groq model decide verdict and team (rejected: non-deterministic, harder to audit, slower)
2. **Rule-Only Verdict**: Ignore patterns, only use rule violations (rejected: misses sophisticated ML schemes)
3. **Multi-Team Assignment**: Assign to multiple teams simultaneously (rejected: spec requires "exactly one team")

**Implementation Logic**:
```python
def calculate_verdict(triggered_rules: List[Rule], detected_patterns: List[Pattern]) -> Tuple[str, str]:
    rule_score = sum(rule.severity_weight for rule in triggered_rules)
    pattern_score = sum(pattern.confidence * pattern.risk_multiplier for pattern in detected_patterns)
    total_score = rule_score + pattern_score

    if total_score >= 70:
        verdict = "fail"
    elif total_score >= 30:
        verdict = "suspicious"
    else:
        verdict = "pass"

    # Team assignment
    if any(rule.type in ["sanctions", "prohibited_jurisdiction", "regulatory_threshold"] for rule in triggered_rules):
        team = "legal"
    elif detected_patterns or any(rule.type == "edd_trigger" for rule in triggered_rules):
        team = "compliance"
    elif any(rule.type == "data_quality" for rule in triggered_rules):
        team = "front_office"
    else:
        team = "compliance"  # default

    return verdict, team
```

### 4. Pattern Detection Strategies

**Decision**: Rule-based pattern detectors with configurable thresholds

**Rationale**:
- **5 Core Patterns** (per SC-005 success criteria):
  1. **Structuring**: Multiple transactions just below $10K threshold in 24h window
  2. **Velocity**: Abnormal transaction frequency (>5σ from historical mean)
  3. **Jurisdictional Risk**: High concentration in FATF blacklist countries
  4. **Round-Tripping**: Circular flow (A→B→C→A) within 7-day window
  5. **Layering**: Complex multi-hop transactions masking source
- **Threshold Configuration**: Patterns use configurable thresholds (environment variables)
- **Historical Baseline**: Compare current payment to 90-day moving average for velocity/amount anomalies

**Alternatives Considered**:
1. **ML-Based Anomaly Detection**: Train scikit-learn model on historical data (rejected: insufficient training data for hackathon, model drift issues)
2. **LLM Pattern Recognition**: Ask Groq to identify patterns from raw transaction list (rejected: non-deterministic, expensive token usage, slower)
3. **Graph Database**: Use Neo4j for network analysis (rejected: additional infrastructure complexity)

**Pattern Detection Pseudocode**:
```python
def detect_structuring(payment, history):
    # Find transactions in 24h window before payment
    recent_txns = [t for t in history if is_within_24h(t.date, payment.date)]
    total_amount = sum(t.amount for t in recent_txns) + payment.amount

    if all(t.amount < 10000 for t in recent_txns) and total_amount >= 10000:
        return Pattern(type="structuring", confidence=0.9, evidence=recent_txns)
    return None

def detect_velocity(payment, history):
    # 90-day baseline
    baseline = history[-90:]
    mean_frequency = calculate_frequency(baseline)
    std_frequency = calculate_std(baseline)

    current_frequency = count_transactions_last_week(history + [payment])
    z_score = (current_frequency - mean_frequency) / std_frequency

    if z_score > 5:
        return Pattern(type="velocity", confidence=min(z_score/10, 1.0), evidence=...)
    return None
```

### 5. Performance Optimization

**Decision**: Async FastAPI + parallel agent execution + database indexing

**Rationale**:
- **Async Endpoints**: Use `async def` for FastAPI routes to handle 100 concurrent requests
- **Parallel Agent Execution**: LangGraph allows concurrent node execution for rule checker + pattern detector (reduces latency by 40%)
- **Database Indexing**: Create indexes on `payment_history(payer_id, beneficiary_id, date)` and `compliance_rules(jurisdiction, is_active, effective_date)`
- **Connection Pooling**: Supabase connection pool sized to 20 connections (supports 100 concurrent requests with avg 5 queries each)
- **Caching**: Cache active rules per jurisdiction (TTL=5min) to avoid repeated queries

**Performance Budget**:
- Database query: <50ms (indexed lookups)
- Rule checking: <200ms (parallel with pattern detection)
- Pattern detection: <200ms (parallel with rule checking)
- Verdict assignment: <50ms (deterministic logic)
- Alert generation: <50ms (database insert)
- **Total**: <500ms p95 latency (meets SLA)

**Alternatives Considered**:
1. **Redis Cache**: Cache all historical transactions in Redis (rejected: memory cost, stale data risk)
2. **GraphQL**: Use GraphQL for more flexible querying (rejected: REST simpler for hackathon)
3. **Message Queue**: Async processing with Celery (rejected: adds complexity, user expects real-time response)

### 6. Audit Trail & Observability

**Decision**: Structured JSON logging + Prometheus metrics + Langsmith tracing

**Rationale**:
- **Audit Logs**: Append-only `audit_logs` table with columns: `trace_id`, `payment_id`, `verdict`, `team`, `triggered_rules_json`, `detected_patterns_json`, `justification`, `timestamp`, `llm_model`
- **Prometheus Metrics**:
  - `aml_payment_analysis_total{verdict, team}` (counter)
  - `aml_analysis_latency_ms` (histogram)
  - `aml_patterns_detected_total{pattern_type}` (counter)
  - `aml_rules_triggered_total{rule_type}` (counter)
- **Langsmith Tracing**: Every LangGraph workflow tagged with `trace_id` for debugging
- **Structured Logs**: JSON format with fields: `level`, `timestamp`, `trace_id`, `agent_name`, `action`, `duration_ms`, `metadata`

**Alternatives Considered**:
1. **Plain Text Logs**: Use Python logging to file (rejected: harder to query, no structure)
2. **Third-Party APM**: Datadog or NewRelic (rejected: budget constraints, Langsmith sufficient for agents)
3. **Blockchain Audit Trail**: Immutable ledger for compliance (rejected: over-engineered, PostgreSQL append-only sufficient)

### 7. Error Handling & Graceful Degradation

**Decision**: Circuit breakers + fallback strategies + error categorization

**Rationale**:
- **Groq API Failures**: Circuit breaker (3 retries, exponential backoff, 5s timeout) → fallback to rule-only analysis (skip LLM pattern reasoning)
- **Missing Rules Data**: If feature 003 not available, log warning and use pattern-only analysis
- **Missing History Data**: If feature 001 returns empty history (new customer), proceed with rule-only analysis
- **Database Connection Errors**: Retry with exponential backoff (3 attempts), return HTTP 503 if all fail
- **Invalid Payment Data**: Return HTTP 400 with detailed validation error message

**Error Categories**:
1. **User Errors** (4xx): Missing fields, invalid format → return actionable error message
2. **System Errors** (5xx): Database down, LLM timeout → log trace_id, return generic error
3. **Degraded Mode**: Partial data available → complete analysis with reduced confidence, log warning

### 8. Report Generation

**Decision**: Structured JSON reports with optional PDF rendering

**Rationale**:
- **Primary Format**: JSON with sections: `summary`, `payment_details`, `verdict`, `team`, `triggered_rules`, `detected_patterns`, `recommendations`, `audit_metadata`
- **PDF Rendering**: Future enhancement (use ReportLab or WeasyPrint); for hackathon, JSON suffices
- **Aggregate Reports**: SQL query over `verdicts` and `audit_logs` tables with date range filter, group by team/pattern/verdict

**Report Schema**:
```json
{
  "report_id": "uuid",
  "trace_id": "uuid",
  "payment_id": "uuid",
  "timestamp": "ISO8601",
  "verdict": "suspicious",
  "assigned_team": "compliance",
  "risk_score": 45,
  "triggered_rules": [
    {"rule_id": "uuid", "type": "edd_trigger", "severity": "medium", "description": "..."}
  ],
  "detected_patterns": [
    {"type": "velocity", "confidence": 0.85, "evidence": "..."}
  ],
  "recommendations": [
    "Review transaction frequency over past 30 days",
    "Verify source of funds documentation"
  ],
  "audit_metadata": {
    "llm_model": "kimi-k2-0905",
    "analysis_duration_ms": 450,
    "data_sources": ["compliance_rules", "payment_history"]
  }
}
```

## Summary of Key Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| **Architecture** | LangGraph multi-agent with coordinator pattern | Modularity, parallelism, auditability |
| **Integration** | Service layer abstraction for features 001/003 | Loose coupling, graceful degradation |
| **Verdict Logic** | Multi-factor weighted scoring + deterministic team routing | Transparent, auditable, meets spec requirements |
| **Pattern Detection** | Rule-based detectors with configurable thresholds | Deterministic, fast, no ML training needed |
| **Performance** | Async FastAPI + parallel agents + database indexing | <500ms latency target, 100 concurrent requests |
| **Audit Trail** | Structured JSON logs + Prometheus + Langsmith | Full observability, compliance defensibility |
| **Error Handling** | Circuit breakers + fallback strategies | Resilience, graceful degradation |
| **Reports** | Structured JSON (PDF future enhancement) | Hackathon time constraint, JSON covers requirements |

## Open Questions (None)

All technical unknowns resolved through research. Ready to proceed to Phase 1 (Data Model & Contracts).
