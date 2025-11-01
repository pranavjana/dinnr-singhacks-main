# Data Model: PDF Document Processing and Semantic Embedding Pipeline

**Phase**: Phase 1 - Design
**Date**: 2025-11-01
**Source**: Feature specification + research.md findings

---

## Entity Overview

### Document (Core Entity)

Represents a crawled MAS compliance PDF file with extracted content and metadata.

```
Document {
  id: UUID (primary key)
  source_url: String (unique, max 2048 chars)
  filename: String (original filename from crawler)
  file_hash: String (SHA-256, content-based dedup)
  file_size_bytes: Integer (for audit/quota tracking)
  page_count: Integer (extracted from PDF metadata)
  extracted_text: Text (full text content, searchable)

  # Metadata
  ingestion_date: DateTime (when crawler fetched document)
  ingestion_source: String (MAS, CBR, regulatory authority identifier)
  last_updated: DateTime (for versioning/supersession tracking)
  processing_status: Enum (ingested | pending_embedding | embedding_complete | embedding_failed)

  # Quality Metrics
  extraction_confidence: Float (0.0-1.0, based on character count match vs. original)
  is_duplicate: Boolean (flagged if content_hash matches another document)
  canonical_document_id: UUID? (if duplicate, points to original)

  # Relationships
  documents_metadata_id: UUID (foreign key)
  embeddings: List<Embedding> (multiple if chunked)
  processing_logs: List<ProcessingLog> (audit trail)

  # Constraints
  source_url != null (required, trace to source)
  file_hash unique (prevent duplicate storage)
  created_at: DateTime (immutable timestamp)
}
```

### DocumentMetadata (Structured Info)

Stores validated metadata extracted from document content or crawler headers.

```
DocumentMetadata {
  id: UUID (primary key)
  document_id: UUID (foreign key to Document)

  # Content Classification
  document_type: Enum (circular | notice | guideline | policy | other)
  effective_date: Date? (when regulation takes effect)
  expiry_date: Date? (when regulation expires)
  regulatory_framework: String[] (e.g., ["AML", "KYC", "CTF"])

  # Language & Accessibility
  primary_language: Enum (english | chinese | multilingual)
  has_chinese_content: Boolean
  is_encrypted: Boolean (if password-protected)
  ocr_required: Boolean (if image-only sections)

  # Source Attribution (Compliance Critical)
  issuing_authority: String (e.g., "Monetary Authority of Singapore")
  circular_number: String? (e.g., "MAS/NOTICE/2024-01")
  version: String (for document revisions)

  # Processing Quality
  extraction_method: Enum (pdfplumber | pypdf_fallback | manual_upload)
  validation_status: Enum (validated | requires_review | validation_failed)

  created_at: DateTime (immutable)
}
```

### Embedding (Vector Representation)

Stores semantic vector embeddings and associated metadata for vector search.

```
Embedding {
  id: UUID (primary key)
  document_id: UUID (foreign key to Document)

  # Vector Data
  embedding_vector: Vector(768) (Gemini embedding dimension)
  chunk_index: Integer (0 for full doc, 1+ for chunked content)
  content_length: Integer (tokens in chunked content)

  # Metadata
  embedding_model: String (e.g., "models/embedding-001")
  embedding_model_version: String (for model tracking/versioning)
  embedding_timestamp: DateTime (when embedding was created)

  # Chunk Content (for snippet generation)
  chunk_text: Text (the actual text that was embedded, up to 5K chars)
  chunk_start_page: Integer (page number in original PDF)

  # Quality Tracking
  retry_count: Integer (0 if first attempt, 1+ if retried)
  embedding_cost_usd: Decimal (for cost tracking)

  # Indexing
  created_at: DateTime (immutable)

  # Indexes
  HNSW index on embedding_vector (vector similarity search)
  B-tree on (document_id, chunk_index) for retrieval
}
```

### ProcessingLog (Immutable Audit Trail)

Records every processing event for compliance defensibility.

```
ProcessingLog {
  id: UUID (primary key)
  document_id: UUID (foreign key to Document)

  # Event Details
  event_type: Enum (ingested | extraction_started | extraction_completed |
                    extraction_failed | dedup_check | embedding_queued |
                    embedding_started | embedding_completed | embedding_failed |
                    embedding_retried)

  timestamp: DateTime (when event occurred)
  processor_version: String (e.g., "pdf-processor-v1.0.0")

  # Status & Outcome
  status: Enum (success | partial_success | failure)
  error_message: String? (if failed)

  # For Embedding Events
  embedding_model: String?
  embedding_model_version: String?
  tokens_used: Integer?
  api_latency_ms: Integer?
  retry_attempt: Integer? (1, 2, 3)
  retry_next_time: DateTime? (scheduled next retry)

  # Audit Context
  user_id: String? (if manually triggered, null for automated)
  api_endpoint: String? (which API call triggered this)

  # Constraints
  created_at: DateTime (immutable, log-append only)
  [NO UPDATE/DELETE - audit trail is immutable]
}
```

---

## State Transitions

### Document Processing States

```
Diagram:

┌─────────┐
│ingested │
└────┬────┘
     │
     v
┌──────────────────┐
│pending_embedding │ ◄────────────────┐
└────┬─────────────┘                  │
     │                        (retry, exponential backoff)
     ├─ success ──────────────────┐
     │                            │
     │                      ┌─────v──────────────┐
     │                      │embedding_complete  │
     │                      └───────────────────┘
     │
     └─ failure ────┐
                    │
              ┌─────v──────┐
              │pending_     │ (attempt < 3)
              │embedding    │ (wait 30 min → 4 hrs → 24 hrs)
              └─────────────┘
```

**Trigger Events**:
- `ingested`: Document added to database
- `pending_embedding`: Embedding task queued (immediate for new docs, batch for annual refresh)
- `embedding_complete`: Gemini API returned valid vector
- `embedding_failed`: Gemini API error, scheduled retry with exponential backoff

### Duplicate Detection (Workflow)

```
1. New PDF arrives
2. Calculate SHA-256 of extracted text
3. Check if file_hash exists in Document table
4. If match found:
   - Mark new doc as duplicate (is_duplicate=true)
   - Set canonical_document_id = existing doc
   - Log dedup_check event
   - Do NOT create embedding (avoid API cost)
5. If no match:
   - is_duplicate = false
   - Proceed with embedding
```

---

## Validation Rules

### Document Entity

| Field | Validation | FR/SC Reference |
|-------|-----------|-----------------|
| `source_url` | Must be valid HTTP(S) URL, max 2048 chars | FR-006 (source traceability) |
| `file_hash` | Must be unique (content-based dedup) | FR-003 (duplicate detection) |
| `extraction_confidence` | 0.0 ≤ confidence ≤ 1.0 | FR-002 (accuracy validation) |
| `file_size_bytes` | > 0 and < 500MB | (reasonable PDF size constraint) |
| `page_count` | > 0 | (validate PDF extraction worked) |

### Embedding Entity

| Field | Validation | FR/SC Reference |
|-------|-----------|-----------------|
| `embedding_vector` | Must have exactly 768 dimensions | FR-004 (Gemini embedding contract) |
| `chunk_index` | Integer ≥ 0 | (chunk tracking) |
| `retry_count` | Integer, 0 ≤ retry_count ≤ 3 | FR-012 (exponential backoff limit) |
| `embedding_cost_usd` | Decimal, ≥ 0 | SC-008 (cost optimization tracking) |

### ProcessingLog Entity

| Field | Validation | FR/SC Reference |
|-------|-----------|-----------------|
| `timestamp` | UTC, with timezone | FR-008 (audit timestamp) |
| `processor_version` | Semantic versioning (e.g., "1.0.0") | FR-008 (version tracking) |
| `created_at` | Immutable, cannot be modified | Principle III (Audit Trail First) |

---

## Relationships & Cardinality

```
Document (1) ──────→ (1) DocumentMetadata
           │
           │
           └──────→ (*) Embedding
           │
           └──────→ (*) ProcessingLog


Key Constraints:
- Each Document has exactly 1 DocumentMetadata (1:1)
- Each Document can have multiple Embeddings (1:*) — one for full doc, more for chunks
- Each Document can have many ProcessingLog entries (1:*) — audit trail grows over time
- Embeddings are immutable (no updates, only inserts)
- ProcessingLog is append-only (no updates, only inserts)
```

---

## Indexes & Query Optimization

### Indexes Required (Performance SC-001, SC-002, SC-006)

```sql
-- Document table
CREATE INDEX idx_document_source_url ON document(source_url);  -- FR-006 (filtering)
CREATE INDEX idx_document_file_hash ON document(file_hash);    -- FR-003 (dedup detection)
CREATE INDEX idx_document_ingestion_date ON document(ingestion_date);  -- Audit filtering
CREATE INDEX idx_document_status ON document(processing_status);  -- Monitoring

-- DocumentMetadata table
CREATE INDEX idx_metadata_regulatory_framework ON document_metadata USING GIN(regulatory_framework);  -- Category filtering

-- Embedding table
CREATE INDEX idx_embedding_document_id ON embedding(document_id);  -- Fast retrieval
CREATE INDEX idx_embedding_chunk_index ON embedding(document_id, chunk_index);  -- Chunk lookup
-- pgvector HNSW index (for vector similarity)
CREATE INDEX idx_embedding_vector_hnsw ON embedding USING hnsw(embedding_vector vector_cosine_ops);

-- ProcessingLog table
CREATE INDEX idx_processing_log_document ON processing_log(document_id);  -- Audit trail retrieval
CREATE INDEX idx_processing_log_timestamp ON processing_log(timestamp);  -- Time-range queries
```

### Query Performance Targets

| Operation | Target | SC Reference |
|-----------|--------|--------------|
| Search (semantic) | <500ms p95 | SC-002 |
| Document retrieval | <50ms | SC-006 |
| Audit log query | <100ms | SC-005 |
| Batch processing (50 docs) | <1 hour | SC-001 |

---

## Migration & Schema Versioning

### Initial Migration (v1.0)

```python
# Schema versioning in config
SCHEMA_VERSION = "1.0"

# Migration path
0. Create extensions (pgvector)
1. Create Document table
2. Create DocumentMetadata table
3. Create Embedding table
4. Create ProcessingLog table
5. Create indexes
6. Seed initial data if any
```

### Future Compatibility

- Add `schema_version` column to Embedding for model version tracking
- Add `content_hash` to detect document content changes (for supersession)
- Plan for Embedding model upgrade (new dimension size or algorithm)

---

## Data Lifecycle & Retention

### Document Retention Policy

- **Documents**: Retain indefinitely (compliance audit history is valuable)
- **Embeddings**: Retain current + 2 prior versions (for audit trail during annual refresh)
- **ProcessingLog**: Retain indefinitely (immutable audit trail)

### Supersession Handling (Edge Case)

When a newer version of a regulatory document is released:

1. Crawler detects new version at same URL or via metadata
2. Create new Document entry (don't overwrite)
3. Mark old Document with `last_updated` and optional `superseded_by` reference
4. Both searchable, but search results can filter for "latest versions only"

---

## Relationships to Feature Requirements

| Entity | FR Coverage | Design Feature |
|--------|-------------|-----------------|
| Document | FR-001, FR-002, FR-003, FR-005, FR-006, FR-014 | Extracted text, file hash dedup, source attribution |
| DocumentMetadata | FR-006, FR-008 | Regulatory framework, processing version |
| Embedding | FR-004, FR-007, FR-009 | Vector storage, model versioning, search capability |
| ProcessingLog | FR-008, FR-012 | Immutable audit trail, retry tracking |
| State Machine | FR-011, FR-012 | Immediate embedding + annual refresh, exponential backoff |

---

## Next Steps (Phase 2)

- API contracts (document_api.yaml, search_api.yaml)
- Pydantic schema definitions for request/response DTOs
- SQLAlchemy ORM mappings
- Database migration scripts
