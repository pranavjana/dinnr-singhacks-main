# Quickstart Guide: Rules-Based Payment Analysis Integration

**Feature**: 004-rules-payment-integration
**Audience**: Backend developers, DevOps engineers
**Estimated Setup Time**: 30 minutes

## Prerequisites

Before starting, ensure you have:

- [ ] Python 3.11+ installed (`python --version`)
- [ ] Access to Supabase PostgreSQL database (connection string)
- [ ] Groq API key for Kimi K2-0905 model
- [ ] Features 001 (payment-history-analysis) and 003 (langgraph-rule-extraction) deployed or available
- [ ] Docker installed (optional, for containerized deployment)

## Quick Start (5 minutes)

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Required packages** (add to `backend/requirements.txt`):
```txt
fastapi==0.110.0
uvicorn[standard]==0.28.0
langgraph==0.1.0
langchain==0.1.0
pydantic==2.6.0
supabase==2.3.0
groq==0.4.2
pandas==2.2.0
prometheus-client==0.20.0
structlog==24.1.0
tenacity==8.2.3  # for retries/circuit breakers
```

### 2. Configure Environment

Create `backend/.env`:

```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
DATABASE_URL=postgresql://user:password@host:5432/dbname

# LLM
GROQ_API_KEY=your-groq-api-key
LLM_MODEL=kimi-k2-0905

# Application
ENVIRONMENT=development
LOG_LEVEL=INFO

# Performance
MAX_CONCURRENT_REQUESTS=100
DATABASE_POOL_SIZE=20
ANALYSIS_TIMEOUT_SECONDS=30

# Pattern Detection Thresholds
STRUCTURING_THRESHOLD=10000
VELOCITY_SIGMA_THRESHOLD=5
HIGH_RISK_JURISDICTIONS=KP,IR,SY,MM  # North Korea, Iran, Syria, Myanmar

# Observability
LANGSMITH_API_KEY=your-langsmith-key  # optional
ENABLE_METRICS=true
METRICS_PORT=9090
```

### 3. Database Migration

Run migration to create tables (verdicts, alerts, triggered_rules, detected_patterns, audit_logs):

```bash
# Create migration file
cat > backend/migrations/004_payment_analysis_tables.sql << 'EOF'
-- See data-model.md for full schema

-- Verdicts table
CREATE TABLE verdicts (
    verdict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,
    trace_id UUID NOT NULL UNIQUE,
    verdict VARCHAR(20) NOT NULL CHECK (verdict IN ('pass', 'suspicious', 'fail')),
    assigned_team VARCHAR(20) NOT NULL CHECK (assigned_team IN ('front_office', 'compliance', 'legal')),
    risk_score DECIMAL(5, 2) NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    rule_score DECIMAL(5, 2) NOT NULL,
    pattern_score DECIMAL(5, 2) NOT NULL,
    justification TEXT NOT NULL,
    analysis_duration_ms INTEGER NOT NULL,
    analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    llm_model VARCHAR(100) NOT NULL DEFAULT 'kimi-k2-0905',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verdicts_payment ON verdicts(payment_id);
CREATE INDEX idx_verdicts_trace ON verdicts(trace_id);
CREATE INDEX idx_verdicts_verdict ON verdicts(verdict, assigned_team);
CREATE INDEX idx_verdicts_timestamp ON verdicts(analysis_timestamp DESC);

-- Alerts table
CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict_id UUID NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,
    assigned_team VARCHAR(20) NOT NULL CHECK (assigned_team IN ('front_office', 'compliance', 'legal')),
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'under_review', 'resolved', 'escalated')),
    triggered_rule_ids UUID[] DEFAULT '{}',
    detected_pattern_types TEXT[] DEFAULT '{}',
    investigation_steps JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_to VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_verdict ON alerts(verdict_id);
CREATE INDEX idx_alerts_payment ON alerts(payment_id);
CREATE INDEX idx_alerts_team_status ON alerts(assigned_team, status);
CREATE INDEX idx_alerts_priority ON alerts(priority, created_at DESC);

-- Triggered rules (junction table)
CREATE TABLE triggered_rules (
    triggered_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict_id UUID NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    rule_id UUID NOT NULL REFERENCES compliance_rules(id) ON DELETE RESTRICT,
    rule_type VARCHAR(100) NOT NULL,
    jurisdiction VARCHAR(10) NOT NULL,
    regulator VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    evidence JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(verdict_id, rule_id)
);

CREATE INDEX idx_triggered_rules_verdict ON triggered_rules(verdict_id);
CREATE INDEX idx_triggered_rules_rule ON triggered_rules(rule_id);
CREATE INDEX idx_triggered_rules_type ON triggered_rules(rule_type);

-- Detected patterns
CREATE TABLE detected_patterns (
    pattern_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verdict_id UUID NOT NULL REFERENCES verdicts(verdict_id) ON DELETE CASCADE,
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE CASCADE,
    pattern_type VARCHAR(50) NOT NULL CHECK (pattern_type IN ('structuring', 'velocity', 'jurisdictional', 'round_tripping', 'layering')),
    confidence DECIMAL(3, 2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence JSONB NOT NULL,
    description TEXT NOT NULL,
    risk_multiplier DECIMAL(4, 2) NOT NULL DEFAULT 1.0 CHECK (risk_multiplier >= 0 AND risk_multiplier <= 10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_detected_patterns_verdict ON detected_patterns(verdict_id);
CREATE INDEX idx_detected_patterns_payment ON detected_patterns(payment_id);
CREATE INDEX idx_detected_patterns_type ON detected_patterns(pattern_type);

-- Audit logs (append-only)
CREATE TABLE audit_logs (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id UUID NOT NULL,
    payment_id UUID NOT NULL REFERENCES payments(payment_id) ON DELETE RESTRICT,
    verdict_id UUID REFERENCES verdicts(verdict_id) ON DELETE RESTRICT,
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(200) NOT NULL,
    decision_type VARCHAR(100) NOT NULL,
    decision_rationale TEXT NOT NULL,
    regulatory_references TEXT[] DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    llm_model VARCHAR(100),
    reasoning_chain JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

CREATE INDEX idx_audit_logs_trace ON audit_logs(trace_id);
CREATE INDEX idx_audit_logs_payment ON audit_logs(payment_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
EOF

# Apply migration
psql $DATABASE_URL -f backend/migrations/004_payment_analysis_tables.sql
```

### 4. Start the Service

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Expected output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 5. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Submit payment for analysis
curl -X POST http://localhost:8000/api/v1/payments/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "originator_name": "Jennifer Parker",
    "originator_account": "GB39OOLA52427580832378",
    "originator_country": "GB",
    "beneficiary_name": "George Brown",
    "beneficiary_account": "GB88KUDJ48147748190437",
    "beneficiary_country": "SG",
    "amount": 5000.00,
    "currency": "USD",
    "transaction_date": "2025-11-01T10:30:00Z",
    "value_date": "2025-11-01T10:30:00Z",
    "swift_message_type": "MT103",
    "sanctions_screening_result": "PASS"
  }'
```

**Expected response** (pass verdict):
```json
{
  "payment_id": "123e4567-e89b-12d3-a456-426614174000",
  "trace_id": "789e4567-e89b-12d3-a456-426614174111",
  "verdict": "pass",
  "assigned_team": "compliance",
  "risk_score": 15,
  "justification": "No rule violations or suspicious patterns detected.",
  "analysis_duration_ms": 380,
  "triggered_rules": [],
  "detected_patterns": []
}
```

## Development Workflow

### Project Structure

```
backend/
├── agents/
│   └── aml_monitoring/
│       ├── payment_analysis_agent.py      # Main LangGraph workflow
│       ├── rule_checker_agent.py          # Rule evaluation sub-agent
│       ├── pattern_detector_agent.py      # Pattern detection sub-agent
│       ├── verdict_router.py              # Verdict/team assignment logic
│       └── state_schemas.py               # Pydantic state definitions
├── routers/
│   └── payment_analysis.py                # FastAPI endpoints
├── services/
│   ├── rules_service.py                   # Interface to feature 003
│   ├── history_service.py                 # Interface to feature 001
│   ├── verdict_service.py                 # Verdict persistence
│   └── alert_service.py                   # Alert generation
├── models/
│   ├── payment.py
│   ├── verdict.py
│   ├── alert.py
│   └── audit.py
├── core/
│   ├── config.py                          # Environment configuration
│   └── observability.py                   # Logging/metrics
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
└── main.py                                 # FastAPI application
```

### Running Tests

```bash
# Unit tests
pytest backend/tests/unit/ -v

# Integration tests (requires database)
pytest backend/tests/integration/ -v

# Contract tests (API endpoints)
pytest backend/tests/contract/ -v

# All tests with coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check backend/

# Type checking
mypy backend/

# Format code
ruff format backend/
```

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/payments/analyze` | POST | Analyze payment for AML risk |
| `/api/v1/verdicts/{id}` | GET | Retrieve verdict by ID |
| `/api/v1/verdicts` | GET | Query verdicts with filters |
| `/api/v1/alerts` | GET | List alerts by team/priority/status |
| `/api/v1/alerts/{id}` | PATCH | Update alert status |
| `/api/v1/reports/payment/{id}` | GET | Generate payment report |
| `/api/v1/reports/aggregate` | GET | Aggregate analysis report |
| `/health` | GET | Service health check |
| `/metrics` | GET | Prometheus metrics |

## Observability

### Metrics (Prometheus)

Access metrics at `http://localhost:9090/metrics`:

```
# Payment analysis metrics
aml_payment_analysis_total{verdict="pass"} 1200
aml_payment_analysis_total{verdict="suspicious"} 85
aml_payment_analysis_total{verdict="fail"} 15

# Latency
aml_analysis_latency_ms_bucket{le="500"} 1180  # p95 < 500ms

# Patterns detected
aml_patterns_detected_total{pattern_type="velocity"} 42
aml_patterns_detected_total{pattern_type="structuring"} 18

# Rules triggered
aml_rules_triggered_total{rule_type="edd_trigger"} 55
```

### Logs (JSON structured)

```json
{
  "level": "info",
  "timestamp": "2025-11-01T10:30:45.123Z",
  "trace_id": "789e4567-e89b-12d3-a456-426614174111",
  "agent_name": "PaymentAnalysisAgent",
  "action": "verdict_assigned",
  "duration_ms": 450,
  "metadata": {
    "verdict": "suspicious",
    "team": "compliance",
    "risk_score": 45
  }
}
```

### Langsmith Tracing

View agent execution traces at https://smith.langchain.com (requires API key):
- Full LangGraph state transitions
- LLM calls with prompts and responses
- Tool invocations and results
- Timing breakdown per node

## Troubleshooting

### Issue: "Database connection failed"

**Solution**:
- Check `DATABASE_URL` in `.env`
- Ensure Supabase PostgreSQL is accessible
- Verify connection pool size: `DATABASE_POOL_SIZE=20`

### Issue: "Groq API timeout"

**Solution**:
- Check `GROQ_API_KEY` is valid
- Increase timeout: `ANALYSIS_TIMEOUT_SECONDS=60`
- Verify Groq API status: https://status.groq.com
- Circuit breaker activates after 3 failures (check logs)

### Issue: "Feature 001/003 integration failure"

**Solution**:
- Ensure features 001 and 003 are deployed
- Check database tables exist: `payment_history`, `compliance_rules`
- Verify service layer queries (see `services/rules_service.py`, `services/history_service.py`)

### Issue: "Analysis latency > 500ms"

**Solution**:
- Check database indexes exist (see migration script)
- Enable query logging: `LOG_LEVEL=DEBUG`
- Review Langsmith traces for slow nodes
- Increase database pool size if connection contention detected

## Next Steps

1. **Run full test suite**: `pytest backend/tests/ -v`
2. **Load test**: Use `locust` or `k6` to verify 100 concurrent requests
3. **Review API contracts**: See `contracts/openapi.yaml` for full specification
4. **Integrate with frontend**: Frontend can consume REST API endpoints
5. **Configure alerts**: Set up Prometheus alerts for SLA violations (<500ms p95)
6. **Review constitution compliance**: See `plan.md` Constitution Check section

## Additional Resources

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Data Model**: See `data-model.md`
- **Research Decisions**: See `research.md`
- **Implementation Plan**: See `plan.md`
- **Feature Spec**: See `spec.md`

## Support

For issues or questions:
- Review logs: `tail -f backend/logs/app.log`
- Check Langsmith traces for agent debugging
- Review Prometheus metrics for performance issues
- Consult `CLAUDE.md` for project-wide conventions
