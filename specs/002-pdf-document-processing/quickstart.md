# Quickstart: PDF Document Processing and Semantic Embedding Pipeline

**Feature**: 002-pdf-document-processing
**Date**: 2025-11-01

This guide helps developers set up and test the PDF document processing backend service locally.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- Supabase project (or self-hosted PostgreSQL + S3)
- Google Cloud account with Gemini API enabled
- Redis (for Celery task queue)
- git

## Installation & Setup

### 1. Clone Repository and Create Backend Environment

```bash
cd /backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

pip install -r requirements.txt
```

### 2. Environment Configuration

Create `.env` file in `/backend` directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/pdf_documents
# or for Supabase:
# DATABASE_URL=postgresql://[user]:[password]@[project].supabase.co:5432/postgres

# Supabase/S3
SUPABASE_URL=https://[project].supabase.co
SUPABASE_KEY=[anon-key]
SUPABASE_SERVICE_ROLE_KEY=[service-role-key]
SUPABASE_BUCKET_NAME=compliance-pdfs

# Gemini API
GOOGLE_API_KEY=[your-gemini-api-key]
GEMINI_MODEL=models/embedding-001

# Redis (for Celery)
REDIS_URL=redis://localhost:6379/0

# FastAPI
FASTAPI_ENV=development
SECRET_KEY=[random-secret-key]
LOG_LEVEL=INFO

# Cors origins (local dev)
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
```

### 3. Database Setup

Initialize PostgreSQL with pgvector:

```bash
# Connect to PostgreSQL
psql -U postgres -d pdf_documents -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
alembic upgrade head
```

### 4. Start Services

```bash
# Terminal 1: FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Celery worker (for background tasks)
celery -A src.tasks worker --loglevel=info

# Terminal 3: Celery beat (for scheduled annual refresh)
celery -A src.tasks beat --loglevel=info

# Terminal 4 (optional): Redis
redis-server  # if not running as service
```

---

## Testing the API

### Test 1: Ingest a Document

```bash
# Create a sample PDF (or use existing)
curl -X POST http://localhost:8000/v1/documents/ingest \
  -F "file=@sample.pdf" \
  -F "source_url=https://mas.org.sg/circular-2024-01" \
  -F "source_name=Monetary Authority of Singapore" \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# Response (202 Accepted):
{
  "document_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "pending_embedding",
  "ingestion_date": "2025-11-01T12:34:56Z",
  "message": "Document queued for embedding. Will be searchable shortly."
}
```

### Test 2: Check Document Status

```bash
curl -X GET http://localhost:8000/v1/documents/550e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# Wait a few seconds, then check again for embedding_complete status
```

### Test 3: Search Documents

```bash
curl -X POST http://localhost:8000/v1/documents/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -d '{
    "query": "what are capital adequacy requirements",
    "k": 5,
    "filters": {
      "min_date": "2024-01-01",
      "max_date": "2025-11-01"
    }
  }'

# Response:
{
  "results": [
    {
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "relevance_score": 0.87,
      "source_url": "https://mas.org.sg/circular-2024-01",
      "ingestion_date": "2025-06-15T10:30:00Z",
      "snippet": "Capital adequacy requirements are..."
    }
  ],
  "query_embedding_timestamp": "2025-11-01T12:34:56Z",
  "execution_time_ms": 234
}
```

### Test 4: Retrieve Audit Trail

```bash
curl -X GET http://localhost:8000/v1/documents/550e8400-e29b-41d4-a716-446655440001/audit-trail \
  -H "Authorization: Bearer ${JWT_TOKEN}"

# Response shows all processing events with timestamps
```

### Test 5: Download Original PDF

```bash
curl -X GET http://localhost:8000/v1/documents/550e8400-e29b-41d4-a716-446655440001/download \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -o downloaded.pdf
```

---

## Generate Test JWT Token

For local testing without Supabase Auth:

```bash
# Generate test JWT (valid for 24 hours)
python -c "
import jwt
import datetime

payload = {
    'sub': 'test-user-123',
    'iat': datetime.datetime.utcnow(),
    'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    'role': 'authenticated'
}

token = jwt.encode(payload, 'your-secret-key', algorithm='HS256')
print(token)
"

export JWT_TOKEN=[generated-token]
```

---

## Running Tests

### Unit Tests

```bash
# Test PDF extraction
pytest tests/unit/test_pdf_extraction.py -v

# Test embedding logic
pytest tests/unit/test_embedding.py -v

# Test search service
pytest tests/unit/test_search.py -v
```

### Integration Tests

```bash
# Full document lifecycle (ingest → extract → embed → search)
pytest tests/integration/test_document_lifecycle.py -v

# Gemini API retry logic with exponential backoff
pytest tests/integration/test_gemini_retry.py -v

# Audit trail immutability
pytest tests/integration/test_audit_trail.py -v
```

### Coverage Report

```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

---

## Directory Structure

```
backend/
├── src/
│   ├── models/
│   │   ├── document.py              # SQLAlchemy ORM models
│   │   └── schemas.py               # Pydantic request/response schemas
│   ├── services/
│   │   ├── pdf_extraction.py        # pdfplumber/pypdf integration
│   │   ├── embedding.py             # Gemini API + retry logic
│   │   ├── document_service.py      # CRUD & audit logging
│   │   └── search_service.py        # Vector search via pgvector
│   ├── api/
│   │   ├── documents.py             # Ingest, GET, download endpoints
│   │   ├── search.py                # Search endpoint
│   │   └── health.py                # Health check & metrics
│   ├── tasks/
│   │   ├── scheduler.py             # APScheduler setup
│   │   ├── immediate_embed.py       # Background embedding task
│   │   └── annual_refresh.py        # Annual batch refresh
│   ├── config.py                    # Settings, environment vars
│   └── main.py                      # FastAPI app initialization
├── tests/
│   ├── unit/
│   │   ├── test_pdf_extraction.py
│   │   ├── test_embedding.py
│   │   └── test_search.py
│   ├── integration/
│   │   ├── test_document_lifecycle.py
│   │   ├── test_gemini_retry.py
│   │   └── test_audit_trail.py
│   └── fixtures.py                  # pytest fixtures
├── migrations/                       # Alembic database migrations
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
└── README.md                         # Detailed backend docs
```

---

## Key Configuration Options

### Performance Tuning

**Processing Rate (SC-001: 50 docs/hour)**:
```python
# In config.py
BATCH_SIZE = 50              # Documents per hour
GEMINI_TIMEOUT_SECONDS = 30  # API call timeout
PDF_EXTRACTION_TIMEOUT = 60  # Max seconds per PDF
```

**Search Performance (SC-002: <500ms)**:
```python
# In config.py
VECTOR_SEARCH_TIMEOUT = 500  # milliseconds
HNSW_EF_SEARCH = 100         # pgvector HNSW parameter
```

### Retry Configuration

```python
# In config.py - FR-012 exponential backoff
MAX_EMBEDDING_RETRIES = 3
RETRY_INITIAL_DELAY = 30     # seconds
RETRY_BACKOFF_MULTIPLIER = 2
RETRY_MAX_DELAY = 86400      # 24 hours
```

### Annual Refresh Cycle

```python
# in config.py - FR-011 scheduling
ANNUAL_REFRESH_SCHEDULE = {
    'day_of_week': 'wednesday',
    'hour': 0,
    'minute': 0,
    'month': 11  # November
}
```

---

## Monitoring & Observability

### Health Check

```bash
curl http://localhost:8000/health

# Response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "gemini_api": "accessible"
}
```

### Prometheus Metrics

Metrics available at `http://localhost:8000/metrics`:

- `pdf_documents_processed_total` - Total documents processed
- `pdf_embeddings_failed_total` - Failed embedding attempts
- `pdf_embeddings_retried_total` - Retry queue depth
- `search_query_latency_ms` - Search execution time
- `api_request_duration_ms` - API endpoint latencies

### Structured Logging

All events logged as JSON to stdout:

```json
{
  "timestamp": "2025-11-01T12:34:56Z",
  "level": "INFO",
  "event": "embedding_completed",
  "document_id": "550e8400-e29b-41d4-a716-446655440001",
  "tokens_used": 5234,
  "latency_ms": 450
}
```

Stream logs to file or log aggregator (Langsmith, CloudLogging):

```bash
# Enable Langsmith integration
export LANGSMITH_API_KEY=[your-key]
export LANGSMITH_PROJECT=pdf-processing
```

---

## Troubleshooting

### Gemini API Key Issues

```bash
# Verify API key
curl https://generativelanguage.googleapis.com/v1beta/models/embedding-001 \
  -H "x-goog-api-key: ${GOOGLE_API_KEY}"
```

### PostgreSQL Connection Issues

```bash
# Test connection
psql -h localhost -U postgres -d pdf_documents -c "SELECT 1;"

# Check pgvector extension
psql -h localhost -U postgres -d pdf_documents -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Redis Connection Issues

```bash
# Test Redis
redis-cli ping  # Should return "PONG"

# Check Celery worker connection
celery -A src.tasks inspect active
```

### Document Not Searchable After Ingestion

1. Check processing status: `GET /documents/{id}` → should be `embedding_complete`
2. Check Celery worker logs for embedding errors
3. Review audit trail: `GET /documents/{id}/audit-trail`
4. Check Gemini API quota in Google Cloud Console

---

## Next Steps

1. Deploy to staging (Docker + Kubernetes recommended)
2. Load test with sample MAS documents (use test fixtures)
3. Verify 99.9% uptime SLA with monitoring
4. Integrate with crawler (webhook at `/documents/ingest`)
5. Add search interface for LLM agents (via Langsmith)

---

## Additional Resources

- [API Contracts](./contracts/) - OpenAPI specifications
- [Data Model](./data-model.md) - Database schema and relationships
- [Research](./research.md) - Technology decisions and rationale
