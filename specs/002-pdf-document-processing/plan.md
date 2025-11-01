# Implementation Plan: PDF Document Processing and Semantic Embedding Pipeline

**Branch**: `002-pdf-document-processing` | **Date**: 2025-11-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-pdf-document-processing/spec.md`

**Note**: This plan implements PDF document ingestion, semantic embedding via Gemini API, vector search, and audit trail capabilities for MAS compliance document management.

## Summary

The PDF Document Processing and Semantic Embedding Pipeline provides a backend service for ingesting MAS compliance PDFs, extracting text with high fidelity, generating semantic embeddings via Google's Gemini API, and enabling natural language semantic search. The system operates in two modes: (1) immediate embedding of new PDFs upon crawler arrival, and (2) annual refresh cycle for re-validation and re-embedding of entire corpus. Complete audit trails and document traceability are maintained throughout. All authenticated components can query and retrieve documents without role-based filtering. The system queues failed embeddings for exponential backoff retry (max 3 attempts/24 hours).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.100+, LangGraph 0.1+, Pydantic, Supabase Python SDK, Google Generative AI SDK (Gemini), pypdf/pdfplumber for text extraction
**Storage**: Supabase PostgreSQL (metadata/audit logs) + S3-compatible storage (PDFs + embeddings), vector search via pgvector extension
**Testing**: pytest with fixtures, integration tests for Gemini API, unit tests for extraction/validation logic
**Target Platform**: Linux server (cloud deployment)
**Project Type**: Backend service (REST API + scheduled tasks)
**Performance Goals**: 50 documents/hour processing rate; semantic search queries <500ms; 5-minute ingestion-to-search SLA
**Constraints**: 3 Gemini API retries/24 hours max; 99.9% uptime over 30 days; 99% document extraction accuracy
**Scale/Scope**: Support thousands of documents; multi-year compliance audit history; multi-language support (English, Chinese)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Required Principles Evaluation

**Principle I (Agentic AI-First)**: ✅ COMPLIANT
- PDF search results will be consumed by LangGraph agents via REST API
- Query results include relevance scores and metadata for agent decision-making
- Audit trails logged for all API calls

**Principle III (Audit Trail & Compliance First)**: ✅ COMPLIANT
- ProcessingLog entity maintains immutable audit trail (timestamp, processor version, embedding model, errors)
- All document operations logged with source traceability
- FR-008 explicitly requires complete audit trails

**Principle V (Security & Data Minimization)**: ✅ COMPLIANT
- Supabase AES-256 encryption at rest; TLS 1.3+ for API calls
- FR-010 validates file signatures and scans for anomalies
- No PII in audit logs (only document metadata)

**Principle VI (Scalable, Observable Backend)**: ✅ COMPLIANT
- FastAPI backend with Prometheus metrics for processed documents
- Structured JSON logging for all embeddings, failures, retries
- SLAs defined: 50 docs/hour (SC-001), <500ms search (SC-002)

**Principle VII (Backend Organization)**: ✅ COMPLIANT
- All backend code in `/backend/` directory per constitution
- REST API contracts for document search
- No frontend coupling

**Status**: ✅ **All constitution requirements satisfied**

## Project Structure

### Documentation (this feature)

```text
specs/002-pdf-document-processing/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (Python PDF libraries, Gemini API patterns, pgvector usage)
├── data-model.md        # Phase 1 output (Document, DocumentMetadata, Embedding, ProcessingLog schemas)
├── quickstart.md        # Phase 1 output (setup, environment, local dev)
├── contracts/           # Phase 1 output (REST API OpenAPI specs)
│   ├── document_api.yaml
│   └── search_api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── document.py          # Document, DocumentMetadata, Embedding, ProcessingLog
│   │   └── schemas.py           # Pydantic schemas for API requests/responses
│   ├── services/
│   │   ├── pdf_extraction.py    # Text extraction, validation, deduplication (pypdf/pdfplumber)
│   │   ├── embedding.py         # Gemini API integration, retry logic, status tracking
│   │   ├── document_service.py  # CRUD operations, audit trail logging
│   │   └── search_service.py    # Semantic search, filtering, ranking
│   ├── api/
│   │   ├── documents.py         # GET /documents, POST /documents/search, GET /documents/{id}
│   │   └── health.py            # Health check, metrics
│   ├── tasks/
│   │   ├── scheduler.py         # APScheduler for annual refresh cycle
│   │   ├── immediate_embed.py   # Background task for new PDFs (webhook from crawler)
│   │   └── annual_refresh.py    # Batch re-embedding of entire corpus
│   ├── config.py                # Environment variables, API keys, settings
│   └── main.py                  # FastAPI app, router setup
└── tests/
    ├── unit/
    │   ├── test_pdf_extraction.py
    │   ├── test_embedding.py
    │   └── test_search.py
    ├── integration/
    │   ├── test_document_lifecycle.py
    │   ├── test_gemini_retry.py
    │   └── test_audit_trail.py
    └── fixtures.py              # pytest fixtures
```

**Structure Decision**: Web/backend-only service structure (Option 2). PDF processing and search are backend-only concerns; the REST API serves frontend agents and external consumers. Scheduled tasks (annual refresh, immediate embedding) are background processes managed by the backend service.

## Next Steps

Phase 0 (Research) and Phase 1 (Design) artifacts will be generated and should include:

- **research.md**: PDF extraction library comparison, Gemini API integration patterns, pgvector setup, exponential backoff implementation
- **data-model.md**: Detailed schema definitions with validation rules and state transitions
- **contracts/**: OpenAPI 3.0 specifications for document management and search APIs
- **quickstart.md**: Local development setup, environment configuration, sample API calls
