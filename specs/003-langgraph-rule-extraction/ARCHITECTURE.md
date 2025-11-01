# LangGraph AML Compliance Rule Extraction Architecture

**Feature ID:** 003-langgraph-rule-extraction
**Status:** Design Phase
**Model:** moonshotai/kimi-k2-instruct-0905 (Groq)
**Last Updated:** 2025-11-01

## Executive Summary

This document defines a two-node LangGraph workflow that transforms embedded regulatory document chunks into structured, versioned AML compliance rules. The system leverages existing document embeddings to guide intelligent chunk retrieval while maintaining full context comprehension through the Kimi K2 model's 128k token window.

---

## 1. System Architecture

### 1.1 Workflow Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌─────────────────┐              │
│  │   Analyser   │────────>│   Rules Tool    │              │
│  │     Node     │         │      Node       │              │
│  └──────┬───────┘         └────────┬────────┘              │
│         │                          │                        │
│         │ Extract Facts            │ Normalize & Store      │
│         │                          │                        │
│  ┌──────▼──────────────────────────▼────────┐              │
│  │         Workflow State (TypedDict)        │              │
│  └───────────────────────────────────────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         │ Read                               │ Write
         ▼                                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Supabase PostgreSQL                       │
├─────────────────────────────────────────────────────────────┤
│  • embeddings (input)                                        │
│  • documents (context)                                       │
│  • compliance_rules (output)                                 │
│  • rule_extractions (audit trail)                            │
│  • extraction_metrics (observability)                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Core Design Principles

1. **Embedding-Guided Retrieval**: Use semantic search to identify relevant chunks, then expand context window for full comprehension
2. **Structured Extraction**: Convert unstructured regulatory text into typed, queryable data structures
3. **Auditability**: Every extraction links back to source document chunks with provenance metadata
4. **Versioning**: Track rule changes over time as new circulars supersede old ones
5. **Modular Scalability**: Add new fact types or jurisdictions without core workflow changes
6. **Measurable Accuracy**: Log confidence scores, validation flags, and human review status

---

## 2. Database Schema Extensions

### 2.1 New Tables

```sql
-- Stores normalized, versioned compliance rules
CREATE TABLE compliance_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_type VARCHAR(100) NOT NULL, -- 'threshold', 'deadline', 'edd_trigger', etc.
    jurisdiction VARCHAR(10) NOT NULL, -- 'SG', 'HK', 'MY', etc.
    regulator VARCHAR(100) NOT NULL, -- 'MAS', 'HKMA', etc.

    -- Rule content (JSONB for flexibility)
    rule_schema_version VARCHAR(10) NOT NULL DEFAULT 'v1',
    rule_data JSONB NOT NULL, -- Structured rule fields

    -- Regulatory metadata
    circular_number VARCHAR(100),
    effective_date TIMESTAMPTZ,
    expiry_date TIMESTAMPTZ,
    supersedes_rule_id UUID REFERENCES compliance_rules(id),

    -- Extraction metadata
    source_document_id UUID NOT NULL REFERENCES documents(id),
    extraction_confidence FLOAT NOT NULL, -- 0.0-1.0
    extraction_model VARCHAR(100) NOT NULL,
    extraction_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Validation and lifecycle
    validation_status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, validated, rejected, archived
    validated_by VARCHAR(100),
    validated_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit trail for every extraction attempt
CREATE TABLE rule_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL, -- Groups related extractions
    document_id UUID NOT NULL REFERENCES documents(id),

    -- Extraction inputs
    embedding_chunks UUID[] NOT NULL, -- Array of embedding IDs used
    prompt_template VARCHAR(50) NOT NULL,
    model_parameters JSONB NOT NULL, -- temperature, max_tokens, etc.

    -- Extraction outputs
    extracted_facts JSONB NOT NULL, -- Raw model output
    created_rules UUID[], -- compliance_rules.id created from this extraction

    -- Performance metrics
    tokens_used INTEGER NOT NULL,
    api_latency_ms INTEGER NOT NULL,
    extraction_cost_usd NUMERIC(10,6) NOT NULL,

    -- Error tracking
    status VARCHAR(20) NOT NULL, -- success, partial, failed
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Observability and quality metrics
CREATE TABLE extraction_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL,

    -- Workflow metadata
    trigger_type VARCHAR(50) NOT NULL, -- scheduled, manual, webhook
    documents_processed INTEGER NOT NULL,
    rules_created INTEGER NOT NULL,
    rules_updated INTEGER NOT NULL,

    -- Quality metrics
    avg_confidence FLOAT NOT NULL,
    validation_pass_rate FLOAT, -- NULL until validation complete
    human_review_required INTEGER NOT NULL,

    -- Performance metrics
    total_duration_ms INTEGER NOT NULL,
    total_cost_usd NUMERIC(10,6) NOT NULL,
    total_tokens_used INTEGER NOT NULL,

    -- Error summary
    failed_documents INTEGER NOT NULL DEFAULT 0,
    error_summary JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_compliance_rules_jurisdiction ON compliance_rules(jurisdiction, rule_type);
CREATE INDEX idx_compliance_rules_effective ON compliance_rules(effective_date, is_active);
CREATE INDEX idx_compliance_rules_document ON compliance_rules(source_document_id);
CREATE INDEX idx_rule_extractions_workflow ON rule_extractions(workflow_run_id);
CREATE INDEX idx_extraction_metrics_created ON extraction_metrics(created_at DESC);
```

### 2.2 Rule Data Schemas (JSONB Examples)

```json
// rule_type: 'threshold'
{
  "threshold_type": "transaction_reporting",
  "amount_sgd": 20000,
  "currency": "SGD",
  "transaction_type": "cash_deposit",
  "applies_to": ["banks", "payment_service_providers"],
  "conditions": ["single_transaction", "linked_transactions_24h"],
  "exemptions": []
}

// rule_type: 'deadline'
{
  "filing_type": "suspicious_transaction_report",
  "deadline_days": 5,
  "deadline_business_days": true,
  "trigger_event": "knowledge_of_suspicion",
  "penalties": "civil_monetary_penalty",
  "applies_to": ["all_financial_institutions"]
}

// rule_type: 'edd_trigger'
{
  "trigger_category": "pep",
  "pep_tier": "foreign_senior_political_figure",
  "relationship_types": ["customer", "beneficial_owner", "authorized_signer"],
  "required_approvals": ["senior_management"],
  "enhanced_measures": [
    "source_of_wealth_verification",
    "ongoing_monitoring_enhanced",
    "periodic_review_12_months"
  ]
}
```

---

## 3. LangGraph Workflow Design

### 3.1 State Schema

```python
from typing import TypedDict, Annotated, Sequence, Literal
from datetime import datetime
import operator

class ExtractionState(TypedDict):
    """Workflow state shared between nodes."""

    # Input configuration
    workflow_run_id: str
    document_id: str
    target_rule_types: list[str]  # ['threshold', 'deadline', 'edd_trigger']
    jurisdiction: str  # 'SG', 'HK', etc.

    # Document context
    document_metadata: dict  # From document_metadata table
    full_text: str  # Complete extracted_text from documents table

    # Analyser outputs
    retrieved_chunks: list[dict]  # Embedding chunks with metadata
    extracted_facts: Annotated[list[dict], operator.add]  # Append-only
    analyser_confidence: float
    analyser_errors: Annotated[list[str], operator.add]

    # Rules Tool outputs
    normalized_rules: list[dict]  # Final compliance_rules records
    rule_ids_created: Annotated[list[str], operator.add]
    rule_ids_updated: Annotated[list[str], operator.add]

    # Workflow control
    current_node: str
    retry_count: int
    status: Literal["running", "completed", "failed", "partial"]

    # Metrics
    tokens_used: Annotated[int, operator.add]
    cost_usd: Annotated[float, operator.add]
    start_time: datetime
    end_time: datetime | None
```

### 3.2 Node: Analyser

**Purpose:** Extract structured AML compliance facts from regulatory documents using embedding-guided retrieval and LLM comprehension.

#### 3.2.1 Inputs
- `state.document_id`: Target document to analyze
- `state.target_rule_types`: Which rule types to extract
- `state.jurisdiction`: Filters relevant regulatory frameworks

#### 3.2.2 Processing Steps

```python
async def analyser_node(state: ExtractionState) -> ExtractionState:
    """
    Step 1: Embedding-based chunk retrieval
    - Query embeddings table with semantic search for each rule_type
    - Example: "transaction reporting thresholds Singapore MAS"
    - Retrieve top-k chunks (k=10) with similarity scores
    - Expand context: fetch adjacent chunks (±2) for continuity

    Step 2: Context assembly
    - Sort chunks by (chunk_start_page, chunk_index)
    - Reconstruct document sections with full context
    - Include document_metadata (effective_date, circular_number)

    Step 3: Fact extraction via Kimi K2
    - Prompt template per rule_type with structured output schema
    - Use JSON mode for reliable parsing
    - Extract multiple facts per rule_type in single call
    - Capture confidence scores for each extracted fact

    Step 4: Validation
    - Check extracted dates are valid
    - Verify amounts have units (SGD, USD, etc.)
    - Flag low-confidence extractions (<0.7) for human review

    Step 5: State update
    - Append extracted_facts with provenance metadata
    - Log chunk IDs used, tokens consumed, confidence scores
    - Increment retry_count if extraction fails
    """
    pass
```

#### 3.2.3 Prompt Engineering

```python
THRESHOLD_EXTRACTION_PROMPT = """
You are an AML compliance expert analyzing {jurisdiction} regulatory documents.

# Document Context
Circular: {circular_number}
Effective Date: {effective_date}
Issuing Authority: {issuing_authority}

# Relevant Text Sections
{chunk_text}

# Task
Extract ALL transaction reporting thresholds mentioned in this document.
For each threshold, provide:

{
  "thresholds": [
    {
      "threshold_type": "transaction_reporting | ctr | str",
      "amount": <numeric>,
      "currency": "SGD|USD|EUR",
      "transaction_type": "cash_deposit|wire_transfer|virtual_asset",
      "applies_to": ["entity_types"],
      "conditions": ["triggering_conditions"],
      "exemptions": ["exemption_categories"],
      "source_text": "exact quote from document",
      "confidence": 0.0-1.0,
      "page_reference": <int>
    }
  ]
}

# Guidelines
- Only extract EXPLICITLY stated thresholds (no inference)
- Include exact source quotes for auditability
- If currency not stated, use {default_currency}
- Mark confidence <0.7 if information is ambiguous
- Return empty array if no thresholds found

Output valid JSON only.
"""
```

#### 3.2.4 Error Handling

| Error Type | Strategy |
|------------|----------|
| **Empty chunk retrieval** | Fallback to full-text search on documents table |
| **JSON parsing failure** | Retry with stricter prompt, log raw output |
| **Low confidence (<0.5)** | Flag for human review, store as `validation_status=pending` |
| **API rate limit** | Exponential backoff, max 3 retries |
| **Partial extraction** | Continue workflow, mark status=partial |

---

### 3.3 Node: Rules Tool

**Purpose:** Normalize extracted facts into versioned compliance_rules and handle updates/supersession.

#### 3.3.1 Inputs
- `state.extracted_facts`: Raw structured data from Analyser
- `state.document_metadata`: Regulatory metadata

#### 3.3.2 Processing Steps

```python
async def rules_tool_node(state: ExtractionState) -> ExtractionState:
    """
    Step 1: Deduplication
    - Query compliance_rules for similar rules (same jurisdiction, rule_type)
    - Use fuzzy matching on rule_data JSONB fields
    - Identify superseded rules (older effective_date, same circular series)

    Step 2: Normalization
    - Convert extracted facts to compliance_rules schema
    - Validate required fields per rule_schema_version
    - Assign extraction_confidence from Analyser

    Step 3: Versioning logic
    - If new circular supersedes old: set old rule.is_active=false
    - Link via supersedes_rule_id
    - Preserve old rules for audit trail

    Step 4: Database writes
    - INSERT INTO compliance_rules
    - INSERT INTO rule_extractions (audit record)
    - UPDATE existing rules if superseded

    Step 5: State update
    - Append rule_ids_created/updated
    - Calculate final metrics (rules created, cost, duration)
    """
    pass
```

#### 3.3.3 Deduplication Strategy

```sql
-- Find potentially duplicate rules
SELECT cr.id, cr.rule_data, cr.effective_date
FROM compliance_rules cr
WHERE cr.jurisdiction = :jurisdiction
  AND cr.rule_type = :rule_type
  AND cr.is_active = true
  AND cr.rule_data @> :search_fragment  -- JSONB containment
ORDER BY cr.effective_date DESC
LIMIT 5;
```

**Business Logic:**
- If `effective_date` is newer and same `circular_number` series → supersession
- If `rule_data` is >90% similar but different source → potential duplicate (flag for review)
- If completely new → create fresh rule

---

## 4. Workflow Orchestration

### 4.1 Graph Definition

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(ExtractionState)

# Add nodes
workflow.add_node("analyser", analyser_node)
workflow.add_node("rules_tool", rules_tool_node)

# Define edges
workflow.set_entry_point("analyser")
workflow.add_edge("analyser", "rules_tool")

# Conditional edge for retries
def should_retry(state: ExtractionState) -> str:
    if state["status"] == "failed" and state["retry_count"] < 3:
        return "analyser"  # Retry from Analyser
    elif state["status"] in ["completed", "partial"]:
        return END
    else:
        return END  # Max retries exceeded

workflow.add_conditional_edges(
    "rules_tool",
    should_retry,
    {
        "analyser": "analyser",
        END: END
    }
)

graph = workflow.compile()
```

### 4.2 Execution Triggers

1. **Scheduled Job**: Daily cron to process new documents added in last 24h
2. **Webhook**: On new document ingestion (from crawler)
3. **Manual**: Admin-triggered reprocessing for specific documents

### 4.3 Batch Processing

For multiple documents:
```python
async def process_document_batch(document_ids: list[str]):
    workflow_run_id = str(uuid.uuid4())
    results = []

    for doc_id in document_ids:
        initial_state = {
            "workflow_run_id": workflow_run_id,
            "document_id": doc_id,
            "target_rule_types": ["threshold", "deadline", "edd_trigger"],
            "jurisdiction": "SG",  # From document_metadata
            # ... initialize other fields
        }

        result = await graph.ainvoke(initial_state)
        results.append(result)

    # Log aggregate metrics
    await log_extraction_metrics(workflow_run_id, results)
    return results
```

---

## 5. Observability & Quality Metrics

### 5.1 Key Metrics

| Metric | Source | Purpose |
|--------|--------|---------|
| **Extraction Coverage** | Rules created / Documents processed | Ensure no documents skipped |
| **Confidence Distribution** | Histogram of `extraction_confidence` | Identify low-quality extractions |
| **Validation Pass Rate** | Validated rules / Total rules | Human-in-loop effectiveness |
| **Cost per Rule** | `total_cost_usd` / `rules_created` | Economic efficiency |
| **API Latency** | `api_latency_ms` percentiles | Model performance |

### 5.2 Dashboards (Future)

- **Quality Dashboard**: Confidence distributions, validation queue
- **Cost Dashboard**: Daily spend trends, per-document cost
- **Audit Log**: Full lineage from PDF → Chunk → Fact → Rule

---

## 6. Supabase MCP Server Integration

### 6.1 Schema Migrations

All schema changes defined in Section 2 will be applied via Supabase MCP:

```python
# Use mcp__supabase__apply_migration tool
migration_name = "003_compliance_rules_tables"
migration_sql = """
-- Content from Section 2.1
CREATE TABLE compliance_rules (...);
CREATE TABLE rule_extractions (...);
CREATE TABLE extraction_metrics (...);
-- Indexes
"""

await mcp.apply_migration(name=migration_name, query=migration_sql)
```

### 6.2 Runtime Data Access

**Read Operations:**
```python
# Fetch chunks for analysis
chunks = await mcp.execute_sql("""
    SELECT e.id, e.chunk_text, e.chunk_start_page, e.embedding_vector
    FROM embeddings e
    WHERE e.document_id = :doc_id
    ORDER BY e.chunk_index
""", params={"doc_id": state["document_id"]})

# Check for duplicate rules
existing_rules = await mcp.execute_sql("""
    SELECT * FROM compliance_rules
    WHERE jurisdiction = :jurisdiction
      AND rule_type = :rule_type
      AND is_active = true
""", params={"jurisdiction": "SG", "rule_type": "threshold"})
```

**Write Operations:**
```python
# Insert new rule
rule_id = await mcp.execute_sql("""
    INSERT INTO compliance_rules
    (rule_type, jurisdiction, regulator, rule_data, source_document_id, ...)
    VALUES (:type, :jurisdiction, :regulator, :data::jsonb, :doc_id, ...)
    RETURNING id
""", params={...})

# Update superseded rules
await mcp.execute_sql("""
    UPDATE compliance_rules
    SET is_active = false, updated_at = NOW()
    WHERE id = :old_rule_id
""", params={"old_rule_id": superseded_id})
```

### 6.3 Advisory Checks

After each migration or major write operation:
```python
# Check for security issues (missing RLS policies)
advisors = await mcp.get_advisors(type="security")

# Check for performance issues (missing indexes)
perf_advisors = await mcp.get_advisors(type="performance")
```

---

## 7. Model-Specific Considerations

### 7.1 Kimi K2 Characteristics

| Feature | Value | Impact on Design |
|---------|-------|------------------|
| **Context Window** | 128k tokens | Can process entire circulars (avg 20-40k tokens) without chunking |
| **JSON Mode** | Supported via Groq | Reliable structured output extraction |
| **Latency** | ~2-5s per request | Acceptable for batch processing |
| **Cost** | $0.30/1M input tokens | Budget ~$0.01-0.05 per document |

### 7.2 Prompt Optimization

- **Few-shot examples**: Include 2-3 annotated examples per rule_type
- **Output schema**: Provide TypeScript/JSON schema for structured extraction
- **Chain-of-thought**: For complex rules (e.g., nested conditions), ask model to explain reasoning before JSON output

---

## 8. Testing & Validation Strategy

### 8.1 Unit Tests

- **Analyser Node**: Mock embeddings retrieval, validate fact extraction format
- **Rules Tool Node**: Test deduplication logic, versioning, JSONB normalization

### 8.2 Integration Tests

- **End-to-end workflow**: Process sample MAS circular, verify rules in database
- **Supabase MCP**: Test migrations, RLS policies, query performance

### 8.3 Quality Assurance

- **Golden dataset**: 20 manually annotated circulars with expected rules
- **Accuracy metrics**: Precision/Recall on threshold extraction
- **Confidence calibration**: Compare model confidence to human validation pass rate

---

## 9. Future Enhancements

1. **Multi-jurisdiction Support**: Extend to HKMA, BNM (Malaysia), OJK (Indonesia)
2. **Cross-reference Detection**: Link related rules across circulars
3. **Change Impact Analysis**: Highlight how new circulars modify existing rules
4. **Human-in-Loop UI**: Review queue for low-confidence extractions
5. **RAG for Q&A**: "What is the STR filing deadline in Singapore?"

---

## 10. Implementation Checklist

- [ ] Apply Supabase migrations (Section 2)
- [ ] Implement `ExtractionState` TypedDict
- [ ] Build `analyser_node` with embedding retrieval
- [ ] Create prompt templates for each rule_type
- [ ] Implement `rules_tool_node` with deduplication
- [ ] Define LangGraph workflow with retry logic
- [ ] Add observability logging to `extraction_metrics`
- [ ] Write unit tests for both nodes
- [ ] Run integration test on 5 sample documents
- [ ] Deploy scheduled job for daily processing

---

## Appendix A: File Structure

```
backend/
├── src/
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── rule_extraction.py          # LangGraph workflow definition
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── analyser.py             # Analyser node
│   │   │   ├── rules_tool.py           # Rules Tool node
│   │   ├── prompts/
│   │   │   ├── threshold_extraction.txt
│   │   │   ├── deadline_extraction.txt
│   │   │   ├── edd_trigger_extraction.txt
│   │   ├── schemas/
│   │   │   ├── extraction_state.py     # TypedDict definition
│   │   │   ├── rule_schemas.py         # JSONB validation schemas
│   ├── services/
│   │   ├── embeddings_service.py       # Query embeddings table
│   │   ├── rules_service.py            # CRUD for compliance_rules
│   │   ├── metrics_service.py          # Log to extraction_metrics
│   ├── scripts/
│   │   ├── run_extraction.py           # CLI for manual runs
│   │   ├── scheduled_extraction.py     # Cron job entrypoint
├── tests/
│   ├── workflows/
│   │   ├── test_analyser_node.py
│   │   ├── test_rules_tool_node.py
│   │   ├── test_full_workflow.py
│   ├── fixtures/
│   │   ├── sample_circular_mas.pdf
│   │   ├── golden_rules.json           # Expected output
├── migrations/
│   ├── 003_compliance_rules_tables.sql
```

---

## Appendix B: Cost & Performance Estimates

**Assumptions:**
- 100 MAS circulars per year
- Avg 30k tokens per circular
- Groq Kimi K2: $0.30/1M input, $1.20/1M output
- Avg 5 rules extracted per circular

**Annual Costs:**
- Input: 100 × 30k × $0.30/1M = **$0.90**
- Output: 100 × 2k × $1.20/1M = **$0.24**
- **Total: ~$1.20/year**

**Processing Time:**
- Single document: ~10-15s (retrieval + LLM + DB writes)
- Batch (100 docs): ~20 minutes (with parallel processing)

---

**End of Architecture Document**
