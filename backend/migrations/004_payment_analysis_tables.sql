-- Migration: 004 - Payment Analysis Tables
-- Feature: Rules-Based Payment Analysis Integration
-- Creates tables for verdicts, alerts, triggered_rules, detected_patterns, and audit_logs

-- Verdicts table
CREATE TABLE IF NOT EXISTS verdicts (
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

CREATE INDEX IF NOT EXISTS idx_verdicts_payment ON verdicts(payment_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_trace ON verdicts(trace_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_verdict ON verdicts(verdict, assigned_team);
CREATE INDEX IF NOT EXISTS idx_verdicts_timestamp ON verdicts(analysis_timestamp DESC);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
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

CREATE INDEX IF NOT EXISTS idx_alerts_verdict ON alerts(verdict_id);
CREATE INDEX IF NOT EXISTS idx_alerts_payment ON alerts(payment_id);
CREATE INDEX IF NOT EXISTS idx_alerts_team_status ON alerts(assigned_team, status);
CREATE INDEX IF NOT EXISTS idx_alerts_priority ON alerts(priority, created_at DESC);

-- Triggered rules (junction table)
CREATE TABLE IF NOT EXISTS triggered_rules (
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

CREATE INDEX IF NOT EXISTS idx_triggered_rules_verdict ON triggered_rules(verdict_id);
CREATE INDEX IF NOT EXISTS idx_triggered_rules_rule ON triggered_rules(rule_id);
CREATE INDEX IF NOT EXISTS idx_triggered_rules_type ON triggered_rules(rule_type);

-- Detected patterns
CREATE TABLE IF NOT EXISTS detected_patterns (
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

CREATE INDEX IF NOT EXISTS idx_detected_patterns_verdict ON detected_patterns(verdict_id);
CREATE INDEX IF NOT EXISTS idx_detected_patterns_payment ON detected_patterns(payment_id);
CREATE INDEX IF NOT EXISTS idx_detected_patterns_type ON detected_patterns(pattern_type);

-- Audit logs (append-only)
CREATE TABLE IF NOT EXISTS audit_logs (
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

-- Prevent updates and deletes on audit logs (append-only)
CREATE OR REPLACE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE OR REPLACE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;

CREATE INDEX IF NOT EXISTS idx_audit_logs_trace ON audit_logs(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_payment ON audit_logs(payment_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT ON verdicts, alerts, triggered_rules, detected_patterns, audit_logs TO your_app_user;
