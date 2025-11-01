# Research: PDF Document Processing and Semantic Embedding Pipeline

**Phase**: Phase 0 - Research & Technology Selection
**Date**: 2025-11-01
**Feature**: PDF Document Processing for MAS Compliance

---

## 1. PDF Text Extraction Library Selection

### Decision: `pdfplumber` (primary) + `pypdf` (fallback)

**Rationale**:
- `pdfplumber` excels at table extraction and structured content (critical for regulatory documents with tables/forms)
- Provides layout information preserving document structure (FR-001 requirement)
- Fast and lightweight compared to heavier alternatives like `pdfminer` or `PyPDF2`
- Fallback to `pypdf` if pdfplumber fails on encrypted/malformed PDFs

**Alternatives Considered**:
- **PyPDF2/pypdf**: Good for simple text extraction but poor table handling; considered for fallback only
- **PDFMiner.six**: More robust for complex PDFs but slower, heavier dependency; rejected for baseline but kept as future escalation
- **OCR (Tesseract/Paddle)**: Not selected for initial MVP; image-only PDFs deferred to edge cases (FR-001 assumes text-based)

**Implementation Pattern**:
```python
try:
    content = extract_with_pdfplumber(pdf_file)
except Exception:
    content = extract_with_pypdf(pdf_file)  # fallback
    mark_extraction_confidence_low()
```

**Dependencies**:
- `pdfplumber==0.10.3`
- `pypdf==3.17.0`

---

## 2. Gemini API Integration & Retry Strategy

### Decision: Exponential Backoff with Queue (FR-012 Clarification A)

**Rationale**:
- Aligns with 99.9% uptime requirement (SC-006)
- Prevents API rate limiting and cascading failures
- Maintains document availability by marking "pending_embedding" during retry
- 3 retries over 24 hours allows recovery from transient outages

**Exponential Backoff Formula**:
- Attempt 1: immediate
- Attempt 2: 30 minutes later (2^0 * 30 min)
- Attempt 3: 4 hours later (2^3 * 30 min)
- Attempt 4 (final): 24 hours later (if all else failed)

**Implementation Pattern**:
```python
@retry(
    wait=wait_exponential(multiplier=30, min=30, max=86400),
    stop=stop_after_attempt(3),
    reraise=True
)
def embed_with_gemini(content: str) -> List[float]:
    response = client.embeddings.create(
        model="models/embedding-001",
        content={"parts": [{"text": content}]}
    )
    return response.embedding
```

**Queue Backend**: Celery (with Redis) for background task management

**Dependencies**:
- `google-generativeai==0.3.0`
- `celery==5.3.0`
- `redis==5.0.0`

**Cost Considerations**:
- Gemini API pricing: ~$0.02 per 1M tokens for embeddings
- Estimated 10K documents × 5K tokens avg = 50M tokens/year = ~$1/year + retry overhead

---

## 3. Vector Search & Database

### Decision: Supabase PostgreSQL + pgvector extension

**Rationale**:
- Supabase provides managed PostgreSQL with pgvector pre-installed
- pgvector supports cosine similarity search (industry standard for embeddings)
- Avoids separate vector DB complexity (Pinecone, Weaviate) for MVP scope
- Integrates seamlessly with relational audit logs and metadata
- Can scale to millions of vectors with proper indexing

**Vector Indexing Strategy**:
- HNSW index on embedding vectors for fast nearest-neighbor search
- B-tree indexes on metadata (source_url, ingestion_date) for filtering

**Search Query Pattern**:
```sql
SELECT
    d.id, d.title, e.cosine_similarity(embedding, query_vector) as score
FROM documents d
JOIN embeddings e ON d.id = e.document_id
WHERE e.cosine_similarity(embedding, query_vector) > 0.5
  AND d.source_url LIKE ?  -- optional filtering
  AND d.ingestion_date >= ?  -- optional date range
ORDER BY score DESC
LIMIT 10
```

**Dependencies**:
- `supabase-py==2.0.0`
- `psycopg[binary]==3.1.0` (PostgreSQL driver)
- pgvector extension (pre-installed in Supabase)

---

## 4. Semantic Search API Contract

### Decision: Natural Language Query with Top-K + Metadata (FR-009 Clarification A)

**Rationale**:
- LLM agents can directly construct natural language queries
- Top-K with relevance scores enables agent confidence assessment
- Metadata filtering (source URL, date range) supports compliance audit queries
- Simple REST interface reduces coupling

**API Endpoint**:
```
POST /api/documents/search
Content-Type: application/json

{
  "query": "what are capital adequacy requirements",
  "k": 10,
  "filters": {
    "source_url_pattern": "mas.org.sg/*",
    "min_date": "2024-01-01",
    "max_date": "2025-11-01"
  }
}

Response:
{
  "results": [
    {
      "document_id": "doc-123",
      "relevance_score": 0.87,
      "source_url": "https://mas.org.sg/circular-2024-01",
      "ingestion_date": "2025-06-15",
      "processing_version": "1.0.0",
      "embedding_model": "models/embedding-001",
      "snippet": "...extracted text excerpt..."
    }
  ],
  "query_embedding_timestamp": "2025-11-01T12:34:56Z"
}
```

---

## 5. Pipeline Scheduling & Triggering

### Decision: Immediate Embedding (Webhook) + Annual Refresh (Cron)

**Rationale**:
- New PDFs embedded immediately on crawler arrival ensures current regulatory info is searchable (FR-011 Clarification A)
- Annual refresh (365-day cycle) provides compliance audit checkpoint (FR-011 Clarification B)
- Dual approach balances timeliness with validation cycle requirements

**Scheduling Implementation**:

**Immediate Embedding (Webhook)**:
- Crawler POSTs to `/api/documents/ingest` with PDF file + source URL
- Background task immediately queues embedding (via Celery)
- Document marked "ingested" (not yet searchable until embedding completes)

**Annual Refresh (APScheduler Cron)**:
```python
scheduler = APScheduler()
scheduler.add_job(
    func=annual_refresh_job,
    trigger="cron",
    day=1,  # 1st of month
    month=11,  # November
    hour=0,
    minute=0,
    id="annual_document_refresh"
)
```

**Dependencies**:
- `apscheduler==3.10.0`
- `celery==5.3.0` (already selected for retry queue)

---

## 6. Document Access Control

### Decision: All Authenticated Components (No Role-Based Filtering)

**Rationale**:
- Internal compliance platform with authorized agents only
- Simpler security model (authentication via API key/JWT)
- Can add role-based filtering later if policy changes
- Aligns with FR-013 clarification (all components equal access)

**Auth Implementation**:
- Supabase JWT for API authentication
- All API endpoints require valid JWT token
- No per-document role checks needed for MVP

**Dependencies**:
- Supabase Auth (already configured in project)

---

## 7. Audit Trail & Compliance Logging

### Decision: Immutable ProcessingLog table + JSON structured logging

**Rationale**:
- ProcessingLog entity (FR-008) provides immutable audit trail
- JSON structured logging integrates with observability stack (Langsmith, Prometheus)
- Single source of truth for compliance officer queries

**Logging Schema**:
```json
{
  "timestamp": "2025-11-01T12:34:56Z",
  "document_id": "doc-123",
  "event_type": "embedding_completed",
  "processor_version": "1.0.0",
  "embedding_model": "models/embedding-001",
  "tokens_used": 5234,
  "cost_usd": 0.00104,
  "status": "success",
  "retry_count": 0
}
```

**Dependencies**: Built into Python logging + Supabase

---

## 8. Multi-Language Document Support

### Decision: Gemini API Native Support (No Pre-processing)

**Rationale**:
- Gemini embedding model natively supports 50+ languages including English and Chinese
- No language detection or preprocessing needed
- Embeddings for Chinese and English in same vector space enables cross-language search

**Testing**:
- Include sample Chinese MAS documents in test suite
- Validate that English query returns English and Chinese documents on same topics

**Dependencies**: None additional (Gemini handles natively)

---

## 9. Large Document Handling

### Decision: Chunking + Multiple Embeddings

**Rationale**:
- Gemini API has context limit (~100K characters per request)
- PDFs with thousands of pages need chunking
- Multiple embeddings per document enable section-level search

**Chunking Strategy**:
- Split on logical boundaries (sections, tables)
- Chunk size: ~2000 tokens (~8000 characters)
- Maintain parent document reference for retrieval

**Schema Addition**:
- Add `chunk_index` to Embedding table to track section number

---

## 10. File Signature Validation & Malware Scanning

### Decision: Magic Bytes + Python-Magic + ClamAV Optional

**Rationale**:
- Magic bytes check confirms PDF file type (prevents polyglot files)
- python-magic fast local validation
- ClamAV optional for deeper security scanning (can add if compliance requires)

**Implementation**:
```python
import magic

def validate_pdf_signature(file_bytes):
    mime = magic.from_buffer(file_bytes, mime=True)
    if mime != "application/pdf":
        raise ValueError("Invalid PDF signature")

    # Check PDF header
    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("Missing PDF header")
```

**Dependencies**:
- `python-magic==0.4.27`
- `python-libmagic` (system dependency)
- `clamav` (optional for enhanced scanning)

---

## Summary of Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| **PDF Extraction** | pdfplumber + pypdf | 0.10.3 + 3.17.0 | Table/structure preservation + fallback |
| **Embeddings** | Google Generative AI (Gemini) | 0.3.0 | Multilingual, long-context, compliance-focused |
| **Vector DB** | Supabase + pgvector | (managed) | Integrated relational + vector search |
| **Background Tasks** | Celery + Redis | 5.3.0 + 5.0.0 | Distributed retry queue, exponential backoff |
| **Scheduling** | APScheduler | 3.10.0 | Annual refresh cycle management |
| **File Validation** | python-magic | 0.4.27 | Malware/format detection |
| **API Framework** | FastAPI | 0.100+ | (from constitution) |
| **ORM** | SQLAlchemy + Pydantic | (standard) | Type-safe database models |
| **Testing** | pytest | (standard) | Unit + integration testing |

---

## Open Decisions for Planning Phase

None at this stage. All major technology and architectural decisions have been researched and justified. Phase 1 will detail the data models, API contracts, and implementation patterns.
