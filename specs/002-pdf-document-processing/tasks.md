---
description: "Task list for PDF Document Processing and Semantic Embedding Pipeline implementation"
---

# Tasks: PDF Document Processing and Semantic Embedding Pipeline

**Input**: Design documents from `/specs/002-pdf-document-processing/`
**Prerequisites**: plan.md (required), spec.md (required), data-model.md, contracts/, research.md

**Feature Branch**: `002-pdf-document-processing`
**Tech Stack**: Python 3.11+, FastAPI, Supabase PostgreSQL + pgvector, Gemini API, Celery + Redis

---

## Task Organization by User Story

Tasks are organized to enable independent implementation of each user story. Each story forms a complete, testable increment.

### User Story Priorities (from spec.md)

- **P1 - US1**: Ingest and Validate MAS Compliance Documents (MVP foundation)
- **P1 - US2**: Create Semantic Embeddings for Search and Retrieval (core value)
- **P1 - US3**: Store Documents with Full Audit Trail and Traceability (compliance requirement)
- **P2 - US4**: Enable Future AI Agent Reasoning (advanced capability)

### MVP Scope Recommendation

**Minimum Viable Product**: Implement **User Story 1 (US1)** completely.

This delivers independent value:
- PDFs can be ingested and validated
- Text extraction works reliably
- Duplicate detection prevents redundant storage
- Audit trail captures ingestion events
- System is testable with sample MAS documents

**US2 + US3** (semantic search + audit completeness) should follow immediately to achieve search capability and compliance defensibility.

---

## Phase 1: Setup & Infrastructure

*Prerequisite for all user stories*

### Project Structure & Configuration

- [X] T001 Create backend directory structure per plan.md at `/backend/` with subdirectories: src/, tests/, migrations/, config/

- [X] T002 [P] Initialize Python virtual environment and requirements.txt in `/backend/` with: FastAPI 0.100+, pdfplumber 0.10.3, pypdf 3.17.0, google-generativeai 0.3.0, sqlalchemy, pydantic, supabase-py, celery, redis, pytest

- [X] T003 [P] Create `/backend/config.py` with environment variable configuration: SUPABASE_URL, SUPABASE_KEY, GOOGLE_API_KEY, DATABASE_URL, REDIS_URL, FASTAPI_ENV, SECRET_KEY

- [X] T004 Create `/backend/.env.example` with all required environment variables (no secrets, template only)

- [X] T005 Create `/backend/src/main.py` FastAPI application entry point with CORS middleware, health check endpoint, base router setup

### Database Setup

- [X] T006 Create Alembic migration structure in `/backend/migrations/` with initial revision for schema creation

- [X] T007 Create initial migration script in `/backend/migrations/versions/001_initial_schema.py` that:
  - Creates `documents` table (Document entity from data-model.md)
  - Creates `document_metadata` table (DocumentMetadata entity)
  - Creates `embeddings` table (Embedding entity)
  - Creates `processing_logs` table (ProcessingLog entity)
  - Adds all constraints, indexes, and relationships

- [X] T008 [P] Create PostgreSQL migration for pgvector extension and HNSW index on embeddings table at `/backend/migrations/versions/001_initial_schema.py` (combined with T007)

### Dependencies & Integrations

- [X] T009 [P] Set up Supabase Python SDK connection in `/backend/src/db/supabase_client.py` with auth, bucket management, and connection pooling

- [X] T010 [P] Configure Gemini API client in `/backend/src/config/gemini_config.py` with API key validation and model configuration

- [X] T011 [P] Set up Redis and Celery configuration in `/backend/src/config/celery_config.py` with broker URL, result backend, task serialization

- [X] T012 Create pytest fixtures in `/backend/tests/fixtures.py` for: test database, mock Gemini responses, sample PDFs, test users

### Logging & Monitoring

- [X] T013 Create structured JSON logging configuration in `/backend/src/logging_config.py` with timestamp, level, event, context fields

- [X] T014 [P] Set up Prometheus metrics collection in `/backend/src/metrics.py` with: documents_processed_total, embeddings_failed_total, search_latency_ms, api_request_duration_ms

- [X] T015 Create health check endpoint in `/backend/src/api/health.py` with database, Redis, Gemini API status checks

---

## Phase 2: Foundational Data & Service Layer

*Blocking prerequisites for all user stories*

### Data Models & Schemas

- [X] T016 Create Pydantic request/response schemas in `/backend/src/models/schemas.py`:
  - IngestRequest (file + source_url)
  - IngestedDocumentResponse (document_id + status)
  - DocumentDetail (full metadata + status)
  - SearchRequest (query + k + filters)
  - SearchResult (document_id + relevance_score + metadata)
  - AuditLogEntry (immutable audit event)

- [X] T017 Create SQLAlchemy ORM models in `/backend/src/models/document.py`:
  - Document (id, source_url, file_hash, extracted_text, ingestion_date, processing_status)
  - DocumentMetadata (document_id FK, document_type, effective_date, regulatory_framework)
  - Embedding (document_id FK, embedding_vector, chunk_index, model_version)
  - ProcessingLog (document_id FK, event_type, timestamp, processor_version, status, retry_count)

### Core Services

- [X] T018 Create PDF text extraction service in `/backend/src/services/pdf_extraction.py`:
  - extract_text_with_pdfplumber(file_bytes) → (text, page_count, confidence)
  - fallback extraction using pypdf if pdfplumber fails
  - validate_pdf_signature(file_bytes) → bool (magic bytes + header check)
  - handle corrupted PDFs gracefully with error logging

- [X] T019 Create document service in `/backend/src/services/document_service.py`:
  - create_document(source_url, file_bytes, extracted_text) → Document
  - check_duplicate(file_hash) → Document | None (content-based dedup)
  - get_document(document_id) → DocumentDetail
  - get_document_by_source_url(url) → Document | None
  - list_documents(status, limit, offset) → List[Document]
  - update_processing_status(document_id, status) → None
  - log_processing_event(document_id, event_type, status, details) → ProcessingLog (immutable append)

- [X] T020 [P] Create database connection pooling in `/backend/src/db/connection.py` with SQLAlchemy engine, session factory, connection limits

---

## Phase 3: User Story 1 (P1) - Ingest and Validate MAS Compliance Documents

*Foundation for all downstream features; independently testable*

### Story Goal
Enable reliable PDF ingestion with text extraction, validation, deduplication, and immutable audit trail logging.

### Independent Test Criteria
- Upload 10 sample MAS PDFs with varying sizes (100KB-5MB)
- Verify all PDFs processed successfully
- Verify extracted text content matches source (manual spot check)
- Verify duplicate PDFs identified and flagged correctly
- Verify processing_status transitions: ingested → extraction_completed
- Verify audit trail records ingestion timestamp, processor version, extraction confidence

### Implementation Tasks

#### Endpoints & API Layer

- [ ] T021 Create document ingest endpoint in `/backend/src/api/documents.py`:
  - POST /v1/documents/ingest (multipart/form-data)
  - Accept file + source_url + source_name (optional)
  - Validate file signature (not already encrypted/corrupted)
  - Return IngestedDocumentResponse with document_id + status

- [ ] T022 [P] Create document retrieval endpoint in `/backend/src/api/documents.py`:
  - GET /v1/documents/{document_id}
  - Return DocumentDetail with status, extraction_confidence, is_duplicate
  - Return 404 if document not found

- [ ] T023 Create document audit trail endpoint in `/backend/src/api/documents.py`:
  - GET /v1/documents/{document_id}/audit-trail
  - Return list of ProcessingLog entries (most recent first)
  - Include pagination (limit, offset)

#### Extraction & Validation

- [ ] T024 [US1] Implement PDF text extraction in `/backend/src/services/pdf_extraction.py`:
  - extract_text_with_pdfplumber(file_bytes) → (text, page_count, confidence_score)
  - Calculate extraction_confidence by comparing original char count vs extracted
  - Handle multi-page documents with section preservation
  - Log extraction_confidence in ProcessingLog

- [ ] T025 [US1] Implement extraction fallback in `/backend/src/services/pdf_extraction.py`:
  - If pdfplumber fails: try pypdf_fallback(file_bytes)
  - Mark extraction_method as "pypdf_fallback" in metadata
  - Lower confidence_score for fallback extractions
  - Log all extraction failures with error details

- [ ] T026 [US1] Implement duplicate detection in `/backend/src/services/document_service.py`:
  - Calculate SHA-256 hash of extracted text content (file_hash)
  - Query existing Document by file_hash
  - If match found: mark is_duplicate=true, set canonical_document_id
  - Log dedup_check event with result (duplicate/unique)
  - Return DuplicateResponse (409) if duplicate detected during ingest

#### Background Processing

- [ ] T027 [US1] Create immediate processing task in `/backend/src/tasks/immediate_embed.py`:
  - process_pdf_immediately(file_bytes, source_url, source_name) Celery task
  - Call extract_text_with_pdfplumber()
  - Call check_duplicate() for dedup
  - Create Document record with processing_status="ingested"
  - Log all processing events to ProcessingLog (immutable append)
  - Mark document as extraction_completed before embedding (next story)

- [ ] T028 [US1] Implement Celery task routing in `/backend/src/tasks/scheduler.py`:
  - Register immediate_embed task in Celery app
  - Configure task serialization, routing, retry behavior
  - Set up error handling and dead-letter queue for failed tasks

#### Testing for US1

- [ ] T029 Create unit tests in `/backend/tests/unit/test_pdf_extraction.py`:
  - test_extract_text_with_pdfplumber_success (valid PDF)
  - test_extract_text_with_invalid_pdf_fails_gracefully
  - test_extract_confidence_score_calculation
  - test_pypdf_fallback_on_pdfplumber_failure
  - test_extract_validates_pdf_signature

- [ ] T030 [P] Create unit tests in `/backend/tests/unit/test_document_service.py`:
  - test_create_document_stores_metadata
  - test_check_duplicate_identifies_same_content_hash
  - test_check_duplicate_returns_none_for_new_content
  - test_document_status_transitions_correctly
  - test_processing_log_is_immutable_append_only

- [ ] T031 Create integration tests in `/backend/tests/integration/test_document_lifecycle.py`:
  - test_ingest_endpoint_accepts_pdf_and_returns_document_id
  - test_ingest_with_duplicate_pdf_returns_409_conflict
  - test_extraction_confidence_recorded_in_metadata
  - test_corrupted_pdf_logged_as_extraction_failed
  - test_audit_trail_shows_ingestion_events

---

## Phase 4: User Story 2 (P1) - Create Semantic Embeddings for Search and Retrieval

*Enables semantic search; dependent on US1*

### Story Goal
Generate semantic embeddings via Gemini API with resilient retry logic, enabling natural language document search.

### Independent Test Criteria
- 10 documents embedded successfully via Gemini API
- Search query "capital adequacy requirements" returns relevant documents in top 5 results
- Embedding latency <500ms p95
- Retry mechanism queues failed embeddings and succeeds after 24-hour max window
- Embeddings support cosine similarity search

### Implementation Tasks

#### Gemini API Integration

- [ ] T032 Create embedding service in `/backend/src/services/embedding.py`:
  - embed_with_gemini(content: str, retry_count: int=0) → List[float]
  - Call Google Generative AI SDK with text content
  - Return 768-dim embedding vector
  - Track tokens_used, api_latency_ms for cost/perf monitoring

- [ ] T033 [US2] Implement exponential backoff retry logic in `/backend/src/services/embedding.py`:
  - Decorator: @retry(wait=exponential, stop_after_attempt=3, max_wait=86400)
  - Retry delays: 30 min → 4 hrs → 24 hrs
  - Mark document as "pending_embedding" during retry window
  - Log retry_attempt (1, 2, 3) in ProcessingLog
  - Log retry_next_time with scheduled retry timestamp

- [ ] T034 [US2] Create retry queue management in `/backend/src/tasks/embedding_retry.py`:
  - Query ProcessingLog for failed embeddings (status=embedding_failed)
  - Check if ready for retry (current_time >= retry_next_time)
  - Requeue ready documents via Celery
  - Update ProcessingLog with new retry attempt
  - Never exceed 3 total attempts per document

#### Vector Storage & Search

- [ ] T035 [US2] Create vector store service in `/backend/src/services/vector_store.py`:
  - store_embedding(document_id, embedding_vector, chunk_index) → Embedding
  - query_by_similarity(query_vector, k=10, threshold=0.0) → List[Embedding]
  - Use pgvector HNSW index for fast nearest-neighbor search
  - Return results with cosine_similarity scores ranked highest first

- [ ] T036 [US2] Implement semantic search service in `/backend/src/services/search_service.py`:
  - search_by_natural_language(query: str, k: int, filters: SearchFilters) → List[SearchResult]
  - Embed user query using Gemini API
  - Call query_by_similarity() with query embedding
  - Apply filters (source_url_pattern, date_range, authority)
  - Return SearchResult objects with snippet extraction

- [ ] T037 [US2] Create snippet extraction in `/backend/src/services/search_service.py`:
  - extract_snippet(document_text, query_text, max_chars=500) → str
  - Find context around query terms in document
  - Return surrounding sentences/paragraphs for preview

#### Endpoints & API

- [ ] T038 Create semantic search endpoint in `/backend/src/api/search.py`:
  - POST /v1/documents/search (application/json)
  - Accept SearchRequest: query, k, filters
  - Call search_service.search_by_natural_language()
  - Return SearchResponse with ranked results + execution_time_ms

- [ ] T039 [P] Create download endpoint in `/backend/src/api/documents.py`:
  - GET /v1/documents/{document_id}/download
  - Stream original PDF from S3
  - Include X-Content-Hash header (SHA-256 for integrity verification)

#### Background Processing

- [ ] T040 [US2] Create embedding task in `/backend/src/tasks/immediate_embed.py`:
  - embed_document(document_id, content: str) Celery task
  - Call embed_with_gemini() with exponential backoff retry
  - Store Embedding record(s) - one for full doc, more if chunked
  - Update document processing_status to "embedding_complete"
  - Log embedding_completed event with tokens_used, api_latency_ms

- [ ] T041 [US2] Implement document chunking for large PDFs in `/backend/src/services/document_service.py`:
  - chunk_document_if_needed(content: str, max_tokens: int=2000) → List[str]
  - Split on section boundaries (preserve logical structure)
  - Create multiple Embedding records with chunk_index tracking
  - Store chunk_text for snippet generation

#### Testing for US2

- [ ] T042 Create unit tests in `/backend/tests/unit/test_embedding.py`:
  - test_embed_with_gemini_returns_768_dim_vector
  - test_exponential_backoff_retry_delays_correct
  - test_max_retry_limit_enforced_at_3_attempts
  - test_document_chunking_splits_large_content
  - test_chunk_index_tracking_preserved

- [ ] T043 [P] Create unit tests in `/backend/tests/unit/test_search.py`:
  - test_query_by_similarity_returns_ranked_results
  - test_snippet_extraction_includes_context
  - test_search_filtering_by_date_range
  - test_search_filtering_by_source_url_pattern
  - test_search_cosine_similarity_threshold

- [ ] T044 Create integration tests in `/backend/tests/integration/test_gemini_integration.py`:
  - test_embed_real_document_via_gemini_api (skip if no API key)
  - test_exponential_backoff_retry_logic_with_mock_failures
  - test_search_returns_semantically_relevant_results
  - test_embedding_latency_under_500ms_p95
  - test_retry_queue_processes_failed_embeddings_correctly

---

## Phase 5: User Story 3 (P1) - Store Documents with Full Audit Trail and Traceability

*Compliance requirement; dependent on US1, independent of US2*

### Story Goal
Maintain complete immutable audit trail with source attribution for regulatory defensibility.

### Independent Test Criteria
- Every document operation logged with timestamp, operator, action
- Audit trail is append-only (no updates/deletes)
- Source URL, ingestion date, processing version traceable for every document
- Original PDF retrievable with integrity verification (SHA-256)
- Compliance officer can verify information source and processing history

### Implementation Tasks

#### Audit Trail Service

- [ ] T045 [US3] Create audit service in `/backend/src/services/audit_service.py`:
  - log_event(document_id, event_type, status, details) → ProcessingLog
  - Append-only: never update existing logs, only insert new
  - Include timestamp (UTC), processor_version, embedding_model_version if applicable
  - Store error_message for failed events
  - Track retry_attempt (1, 2, 3) and retry_next_time for scheduled retries

- [ ] T046 [US3] Implement immutability enforcement in `/backend/src/models/document.py`:
  - ProcessingLog table: remove UPDATE/DELETE permissions at DB level
  - Add created_at timestamp (immutable after insertion)
  - Add unique constraint to prevent duplicate log entries
  - Document creation/modification logged to ProcessingLog

#### Metadata & Traceability

- [ ] T047 [US3] Create metadata extraction service in `/backend/src/services/metadata_extractor.py`:
  - Extract from PDF headers: effective_date, expiry_date, issuing_authority, circular_number
  - Classify document_type (circular, notice, guideline, policy, other)
  - Extract regulatory_framework tags (AML, KYC, CTF, etc.)
  - Store in DocumentMetadata for searchability and compliance queries

- [ ] T048 [US3] Implement source traceability in `/backend/src/services/document_service.py`:
  - Store source_url (immutable)
  - Track ingestion_date (immutable)
  - Calculate file_hash for duplicate detection and integrity verification
  - Store processing_version (immutable, set at creation time)
  - Reference ProcessingLog for all subsequent operations

#### Endpoints & API

- [ ] T049 [US3] Enhance document detail endpoint in `/backend/src/api/documents.py`:
  - GET /v1/documents/{document_id}
  - Return DocumentMetadata: issuing_authority, document_type, regulatory_framework, effective_date
  - Return processing_status, extraction_confidence for quality metrics
  - Show last_embedding_timestamp and embedding_model for search capability timestamp

- [ ] T050 [US3] Implement audit trail retrieval endpoint in `/backend/src/api/documents.py`:
  - GET /v1/documents/{document_id}/audit-trail
  - Return list of ProcessingLog entries (chronological, most recent first)
  - Include pagination (limit, offset) for large audit histories
  - Return all fields: event_type, timestamp, processor_version, status, error_message, retry_attempt

#### Testing for US3

- [ ] T051 Create unit tests in `/backend/tests/unit/test_audit_trail.py`:
  - test_processing_log_append_only_never_updates
  - test_event_timestamp_recorded_correctly
  - test_processor_version_immutable_after_creation
  - test_audit_trail_retrieval_by_document_id
  - test_pagination_on_large_audit_histories

- [ ] T052 [P] Create unit tests in `/backend/tests/unit/test_metadata_extractor.py`:
  - test_extract_metadata_from_pdf_headers
  - test_classify_document_type_correctly
  - test_extract_regulatory_framework_tags
  - test_source_url_stored_immutably
  - test_file_hash_calculated_consistently

- [ ] T053 Create integration tests in `/backend/tests/integration/test_audit_trail.py`:
  - test_full_document_lifecycle_logged_to_audit_trail
  - test_compliance_officer_can_trace_document_source
  - test_original_pdf_retrievable_with_hash_verification
  - test_processing_history_complete_and_immutable
  - test_regulatory_framework_filters_audit_results

---

## Phase 6: User Story 4 (P2) - Enable Future AI Agent Reasoning

*Advanced capability; dependent on US1, US2, US3*

### Story Goal
Provide AI agents with structured document content + embeddings for compliance rule extraction and cross-regulatory analysis.

### Independent Test Criteria
- Agent can query documents by regulatory concept (e.g., "capital adequacy")
- Results include full text content + semantic embeddings + metadata
- Agent can cross-reference similar requirements across regulators
- Query results provide sufficient context for rule extraction

### Implementation Tasks

#### Agent-Optimized Queries

- [ ] T054 [US4] Enhance search service for agent consumption in `/backend/src/services/search_service.py`:
  - search_for_agent(query: str, include_embeddings: bool=true) → AgentSearchResult
  - Return full document text (not just snippets)
  - Include embedding vectors for agent reasoning
  - Include regulatory_framework for cross-regulatory comparison
  - Include processing_version and embedding_model for reproducibility

- [ ] T055 [US4] Create agent-specific response schema in `/backend/src/models/schemas.py`:
  - AgentSearchResult: query + results (with full_text, embedding_vector, metadata)
  - Include semantic_similarity_score for agent confidence assessment
  - Include source_authority for multi-regulator comparison

#### Cross-Regulatory Analysis

- [ ] T056 [US4] Create cross-regulator service in `/backend/src/services/cross_regulator.py`:
  - find_similar_requirements(concept: str, regulators: List[str]) → List[ComparisonResult]
  - Search each regulator's documents for similar content
  - Compare embeddings to find semantically equivalent requirements
  - Return ComparisonResult with side-by-side text + similarity scores

- [ ] T057 [US4] Implement regulatory framework tagging in `/backend/src/services/metadata_extractor.py`:
  - Extract regulatory_framework array from document (AML, KYC, CTF, etc.)
  - Store as queryable tag for filtering
  - Enable "show all capital adequacy requirements across MAS, CBR, other regulators"

#### Endpoints for Agents

- [ ] T058 [US4] Create agent search endpoint in `/backend/src/api/search.py`:
  - POST /v1/documents/search-for-agent
  - Accept query, regulators_filter, include_embeddings
  - Return AgentSearchResult with full content + embeddings
  - Support batch queries for efficiency

#### Testing for US4

- [ ] T059 Create integration tests in `/backend/tests/integration/test_agent_reasoning.py`:
  - test_agent_can_query_by_regulatory_concept
  - test_agent_receives_full_text_and_embeddings
  - test_agent_can_cross_reference_regulators
  - test_semantic_similarity_enables_requirement_comparison

---

## Phase 7: Scheduled Tasks & Automation

*Runs concurrently with user stories; required for compliance*

### Annual Refresh Cycle

- [ ] T060 Create annual refresh task in `/backend/src/tasks/annual_refresh.py`:
  - annual_refresh_job() Celery beat task (scheduled yearly, Nov 1 @ 00:00)
  - Query all documents with processing_status != embedding_complete
  - Reprocess each document: extract text, re-embed, verify
  - Update ProcessingLog with refresh_attempt event
  - Report summary: total_documents, successful, failed

- [ ] T061 [P] Create scheduler setup in `/backend/src/tasks/scheduler.py`:
  - APScheduler configuration with Celery beat
  - Register annual_refresh_job on Nov 1 @ 00:00 UTC
  - Configure timezone handling and job persistence
  - Add monitoring: log job start/end, execution time

### Retry Queue Processing

- [ ] T062 Create retry monitoring task in `/backend/src/tasks/embedding_retry.py`:
  - Check every 5 minutes for documents ready to retry (pending_embedding + retry_next_time <= now)
  - Requeue for embedding via Celery
  - Update ProcessingLog with new retry_attempt
  - Alert if retry_count >= 3 (will give up)

---

## Phase 8: Integration Testing & Quality Assurance

*Cross-cutting concern; verifies entire feature*

### End-to-End Testing

- [ ] T063 Create e2e test scenario in `/backend/tests/integration/test_e2e_complete_workflow.py`:
  - Upload 3 sample MAS PDFs (various sizes)
  - Verify extraction and dedup detection
  - Verify embedding completes within SLA (<5 min)
  - Execute semantic search queries
  - Verify audit trail completeness
  - Verify original PDFs retrievable with hash verification

- [ ] T064 [P] Create performance tests in `/backend/tests/integration/test_performance.py`:
  - test_batch_ingest_50_documents_per_hour_target
  - test_search_latency_under_500ms_p95
  - test_embedding_retry_latency_under_SLA
  - test_concurrent_searches_scale_linearly
  - Profile memory/CPU under load

### Code Quality & Coverage

- [ ] T065 Run pytest with coverage reporting in `/backend/`:
  - Target: >=80% code coverage
  - pytest --cov=src --cov-report=html
  - Identify untested edge cases and remediate
  - Generate coverage report for team review

- [ ] T066 [P] Run linting and type checking:
  - Ruff check (per constitution) for Python style
  - mypy for type safety
  - Bandit for security issues
  - Fix all violations before merge

---

## Phase 9: Documentation & Deployment

*Final phase; ready for production*

### Documentation

- [ ] T067 Create API documentation from OpenAPI specs in `/contracts/`:
  - Generate ReDoc documentation
  - Create Postman collection for manual testing
  - Add example requests/responses for all endpoints

- [ ] T068 [P] Create deployment guide in `/backend/README.md`:
  - Environment setup (Supabase, Gemini API key, Redis)
  - Database migration steps
  - Celery worker configuration
  - Monitoring & alerting setup
  - Troubleshooting common issues

- [ ] T069 Create runbook for annual refresh in `/backend/docs/annual_refresh_runbook.md`:
  - Manual trigger if scheduler fails
  - Monitoring during execution
  - Rollback procedure if issues detected
  - Success validation checklist

### Deployment Preparation

- [ ] T070 Create Docker containerization in `/backend/Dockerfile`:
  - Python 3.11 base image
  - Install dependencies from requirements.txt
  - Expose FastAPI port (8000)
  - Define health check

- [ ] T071 [P] Create docker-compose.yml for local dev:
  - FastAPI service
  - PostgreSQL + pgvector extension
  - Redis
  - Network configuration
  - Volume mounts for dev

- [ ] T072 Create GitHub Actions CI/CD workflow in `/.github/workflows/pdf-processing.yml`:
  - Run tests on PR
  - Check coverage >=80%
  - Run linting/type checks
  - Push Docker image on main branch merge

---

## Task Dependencies & Execution Order

### Critical Path (Sequential, blocking other tasks)

```
T001-T005 (Backend setup)
  ↓
T006-T008 (Database schema)
  ↓
T016-T019 (Data models & core services)
  ↓
T021-T028 (US1: Ingest endpoints & extraction)
```

### Parallel Opportunities

**After T019 (core services ready)**:
- T020 (DB connection pooling) - parallel with T021
- T009-T015 (Integrations & logging) - can start after T003
- T029-T031 (US1 tests) - parallel with T021-T028

**After T028 (US1 extraction complete)**:
- T032-T044 (US2: Embeddings) - can run in parallel with T045-T053 (US3: Audit)
- T042-T044 (US2 tests) - parallel with T032-T041
- T051-T053 (US3 tests) - parallel with T045-T050

**Parallel Always**:
- Phase 7 (scheduled tasks) - T060-T062 can run with any user story phase
- Documentation (Phase 9) - T067-T069 can start once endpoints defined

### Estimated Task Count by Story

- **Phase 1 (Setup)**: 15 tasks
- **Phase 2 (Foundation)**: 5 tasks
- **Phase 3 (US1)**: 15 tasks (5 endpoint + 5 extraction + 3 background + 2 testing tiers)
- **Phase 4 (US2)**: 18 tasks (4 Gemini + 4 vector store + 2 endpoints + 3 background + 5 testing)
- **Phase 5 (US3)**: 9 tasks (2 audit + 2 metadata + 2 endpoints + 3 testing)
- **Phase 6 (US4)**: 6 tasks (2 agent services + 2 endpoints + 2 testing)
- **Phase 7 (Automation)**: 3 tasks
- **Phase 8 (QA)**: 2 tasks
- **Phase 9 (Deploy)**: 6 tasks

**Total**: ~79 tasks

---

## Implementation Strategy

### MVP First (Just User Story 1)

Implement in this order for fastest value:
1. Phase 1-2 (Setup + Foundation): ~20 tasks, 2-3 days
2. Phase 3 (US1: Ingest & Validate): ~15 tasks, 3-4 days
3. Phase 8 (Integration Testing): 1 day

**Result**: Fully functional PDF ingestion system with extraction validation and audit trail. **Can be deployed and tested with real MAS documents.**

### Full Feature (All User Stories)

After MVP:
1. Phase 4 (US2: Embeddings): ~18 tasks, 4-5 days
2. Phase 5 (US3: Audit Trail): ~9 tasks, 2 days (mostly parallel with US2)
3. Phase 6 (US4: Agent Support): ~6 tasks, 1-2 days
4. Phase 7 (Automation): ~3 tasks, 1 day (can overlap with earlier phases)
5. Phase 9 (Docs & Deployment): ~6 tasks, 1 day

**Total Estimated Effort**: ~30-35 developer-days for full feature

---

## Test Coverage Plan

| Test Type | Target | User Stories | Example |
|-----------|--------|--------------|---------|
| **Unit** | >=80% coverage | All | test_extract_text_with_pdfplumber_success |
| **Integration** | Workflow coverage | All | test_document_lifecycle (ingest→extract→embed→search) |
| **Performance** | SLA validation | US2 | test_search_latency_under_500ms_p95 |
| **E2E** | Real-world scenario | All | test_e2e_complete_workflow (3 PDFs, search, audit) |
| **Compliance** | Audit trail | US3 | test_original_pdf_retrievable_with_hash_verification |

---

## Notes for Implementation

- **Use absolute file paths** in all tasks; all development happens in `/backend/`
- **Iterative delivery**: Deploy after each user story is complete
- **Constitution alignment**: Every component follows Principle VII (backend organization) and Principle III (audit trail)
- **Error handling**: All tasks must include graceful failure modes and logging
- **Monitoring**: Prometheus metrics and structured JSON logging throughout
- **Testing first**: Unit tests written before implementation for critical paths (PDF extraction, embedding retry, audit logging)
