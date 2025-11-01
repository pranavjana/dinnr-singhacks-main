"""
Pydantic schemas for API requests and responses
Based on contracts/ specification
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# Enums matching database types
class ProcessingStatus(str, Enum):
    """Document processing status states"""
    INGESTED = "ingested"
    PENDING_EMBEDDING = "pending_embedding"
    EMBEDDING_COMPLETE = "embedding_complete"
    EMBEDDING_FAILED = "embedding_failed"


class DocumentType(str, Enum):
    """Type of regulatory document"""
    CIRCULAR = "circular"
    NOTICE = "notice"
    GUIDELINE = "guideline"
    POLICY = "policy"
    OTHER = "other"


class Language(str, Enum):
    """Primary language of document"""
    ENGLISH = "english"
    CHINESE = "chinese"
    MULTILINGUAL = "multilingual"


class ExtractionMethod(str, Enum):
    """Method used for PDF text extraction"""
    PDFPLUMBER = "pdfplumber"
    PYPDF_FALLBACK = "pypdf_fallback"
    MANUAL_UPLOAD = "manual_upload"


class ValidationStatus(str, Enum):
    """Document validation status"""
    VALIDATED = "validated"
    REQUIRES_REVIEW = "requires_review"
    VALIDATION_FAILED = "validation_failed"


class EventType(str, Enum):
    """Processing log event types"""
    INGESTED = "ingested"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    EXTRACTION_FAILED = "extraction_failed"
    DEDUP_CHECK = "dedup_check"
    EMBEDDING_QUEUED = "embedding_queued"
    EMBEDDING_STARTED = "embedding_started"
    EMBEDDING_COMPLETED = "embedding_completed"
    EMBEDDING_FAILED = "embedding_failed"
    EMBEDDING_RETRIED = "embedding_retried"


class EventStatus(str, Enum):
    """Processing event outcome status"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


# Request Schemas

class IngestRequest(BaseModel):
    """Request to ingest a new PDF document"""
    source_url: HttpUrl = Field(..., description="Original URL where PDF was found", max_length=2048)
    ingestion_source: str = Field(..., description="Identifier for the regulatory authority or source system", max_length=256)


class SearchFilters(BaseModel):
    """Optional filters for search queries"""
    source_url_pattern: Optional[str] = Field(None, description="URL pattern to filter by (e.g., 'mas.org.sg/*')")
    min_date: Optional[datetime] = Field(None, description="Minimum ingestion date")
    max_date: Optional[datetime] = Field(None, description="Maximum ingestion date")
    regulatory_framework: Optional[List[str]] = Field(None, description="Filter by regulatory frameworks (e.g., ['AML', 'KYC'])")


class SearchRequest(BaseModel):
    """Request to search documents by natural language query"""
    query: str = Field(..., min_length=1, max_length=2000, description="Natural language search query")
    k: int = Field(10, ge=1, le=100, description="Number of results to return")
    filters: Optional[SearchFilters] = Field(None, description="Optional search filters")


# Response Schemas

class IngestedDocumentResponse(BaseModel):
    """Response after document ingestion"""
    document_id: UUID = Field(..., description="Unique document identifier")
    status: ProcessingStatus = Field(..., description="Processing status")
    ingestion_date: datetime = Field(..., description="When document was ingested")
    message: str = Field(..., description="Human-readable status message")

    class Config:
        from_attributes = True


class DuplicateResponse(BaseModel):
    """Response when duplicate document is detected"""
    error: str = Field(default="Duplicate document detected", description="Error message")
    canonical_document_id: UUID = Field(..., description="ID of the original document this is a duplicate of")
    source_url: HttpUrl = Field(..., description="Source URL of the existing document")
    file_hash: str = Field(..., description="SHA-256 hash that matched existing document")

    class Config:
        from_attributes = True


class DocumentMetadataResponse(BaseModel):
    """Document metadata details"""
    document_type: str = Field(..., description="Type of regulatory document")
    effective_date: Optional[datetime] = Field(None, description="When regulation takes effect")
    expiry_date: Optional[datetime] = Field(None, description="When regulation expires")
    regulatory_framework: List[str] = Field(..., description="Regulatory frameworks (e.g., ['AML', 'KYC'])")
    primary_language: str = Field(..., description="Primary document language")
    has_chinese_content: bool = Field(..., description="Whether document contains Chinese text")
    issuing_authority: str = Field(..., description="Regulatory authority that issued document")
    circular_number: Optional[str] = Field(None, description="Official circular/notice number")
    version: str = Field(..., description="Document version")
    extraction_method: str = Field(..., description="Method used to extract text")
    validation_status: str = Field(..., description="Validation status")

    class Config:
        from_attributes = True


class DocumentDetail(BaseModel):
    """Full document details with metadata"""
    id: UUID = Field(..., description="Document ID")
    source_url: str = Field(..., description="Original source URL")
    filename: str = Field(..., description="Original filename")
    file_hash: str = Field(..., description="SHA-256 content hash")
    file_size_bytes: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Number of pages")
    ingestion_date: datetime = Field(..., description="When document was ingested")
    ingestion_source: str = Field(..., description="Source authority identifier")
    processing_status: str = Field(..., description="Current processing status")
    extraction_confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction quality score")
    is_duplicate: bool = Field(..., description="Whether document is a duplicate")
    canonical_document_id: Optional[UUID] = Field(None, description="ID of original document if duplicate")
    document_metadata: Optional[DocumentMetadataResponse] = Field(None, description="Document metadata")
    created_at: datetime = Field(..., description="When record was created")

    class Config:
        from_attributes = True
        populate_by_name = True


class SearchResult(BaseModel):
    """Single search result with relevance score"""
    document_id: UUID = Field(..., description="Document ID")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    source_url: str = Field(..., description="Original source URL")
    filename: str = Field(..., description="Document filename")
    ingestion_date: datetime = Field(..., description="When document was ingested")
    processing_version: str = Field(..., description="Processor version used")
    embedding_model: str = Field(..., description="Embedding model used")
    snippet: str = Field(..., max_length=1000, description="Text snippet with context")
    regulatory_framework: List[str] = Field(..., description="Regulatory frameworks")

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Response from semantic search"""
    results: List[SearchResult] = Field(..., description="Ranked search results")
    query_embedding_timestamp: datetime = Field(..., description="When query was embedded")
    execution_time_ms: int = Field(..., description="Query execution time in milliseconds")


class AuditLogEntry(BaseModel):
    """Single audit trail entry (immutable)"""
    id: UUID = Field(..., description="Log entry ID")
    document_id: UUID = Field(..., description="Associated document ID")
    event_type: str = Field(..., description="Type of processing event")
    timestamp: datetime = Field(..., description="When event occurred")
    processor_version: str = Field(..., description="Processor version")
    status: str = Field(..., description="Event outcome status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    embedding_model: Optional[str] = Field(None, description="Embedding model if applicable")
    embedding_model_version: Optional[str] = Field(None, description="Embedding model version")
    tokens_used: Optional[int] = Field(None, description="API tokens consumed")
    api_latency_ms: Optional[int] = Field(None, description="API call latency")
    retry_attempt: Optional[int] = Field(None, description="Retry attempt number (1-3)")
    retry_next_time: Optional[datetime] = Field(None, description="Scheduled retry time")
    user_id: Optional[str] = Field(None, description="User who triggered event")
    api_endpoint: Optional[str] = Field(None, description="API endpoint that triggered event")
    created_at: datetime = Field(..., description="When log entry was created")

    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    """Complete audit trail for a document"""
    document_id: UUID = Field(..., description="Document ID")
    total_entries: int = Field(..., description="Total number of audit entries")
    entries: List[AuditLogEntry] = Field(..., description="Audit log entries (most recent first)")


# Agent-Specific Schemas (for US4)

class AgentSearchResult(SearchResult):
    """Enhanced search result for AI agent consumption"""
    full_text: str = Field(..., description="Complete document text")
    embedding_vector: Optional[List[float]] = Field(None, description="Embedding vector if requested")
    semantic_similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score for confidence")
    source_authority: str = Field(..., description="Issuing regulatory authority")


class ComparisonResult(BaseModel):
    """Cross-regulator comparison result"""
    concept: str = Field(..., description="Regulatory concept being compared")
    regulator_a: str = Field(..., description="First regulator")
    regulator_b: str = Field(..., description="Second regulator")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity between requirements")
    text_a: str = Field(..., description="Requirement text from regulator A")
    text_b: str = Field(..., description="Requirement text from regulator B")


# Health Check Schema

class HealthCheckResponse(BaseModel):
    """System health status"""
    status: str = Field(..., description="Overall health status")
    database: str = Field(..., description="Database connection status")
    redis: str = Field(..., description="Redis connection status")
    gemini_api: str = Field(..., description="Gemini API accessibility status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")


# Batch Document Upload Schemas (for local processing workflow)

class EmbeddingData(BaseModel):
    """Embedding data for a single chunk"""
    chunk_index: int = Field(..., ge=0, description="Zero-based chunk index")
    chunk_text: str = Field(..., min_length=1, description="Chunk text content")
    content_length: int = Field(..., gt=0, description="Length of chunk text")
    embedding_vector: List[float] = Field(..., min_length=768, max_length=768, description="768-dimensional embedding vector")
    chunk_start_page: int = Field(default=1, ge=1, description="Starting page number")
    token_count: int = Field(..., ge=0, description="Approximate token count")
    api_latency_ms: int = Field(..., ge=0, description="API call latency in milliseconds")


class DocumentMetadataInput(BaseModel):
    """Optional metadata for document upload"""
    document_type: DocumentType = Field(default=DocumentType.OTHER, description="Type of regulatory document")
    effective_date: Optional[datetime] = Field(None, description="When regulation takes effect")
    expiry_date: Optional[datetime] = Field(None, description="When regulation expires")
    regulatory_framework: List[str] = Field(default=[], description="Regulatory frameworks (e.g., ['AML', 'KYC'])")
    primary_language: Language = Field(default=Language.ENGLISH, description="Primary document language")
    has_chinese_content: bool = Field(default=False, description="Whether document contains Chinese text")
    issuing_authority: str = Field(..., min_length=1, max_length=512, description="Regulatory authority that issued document")
    circular_number: Optional[str] = Field(None, max_length=128, description="Official circular/notice number")
    version: str = Field(default="1.0", max_length=64, description="Document version")


class BatchDocumentUpload(BaseModel):
    """Request to upload a document with pre-computed embeddings"""
    filename: str = Field(..., min_length=1, max_length=512, description="Original filename")
    source_url: str = Field(..., min_length=1, max_length=2048, description="Source URL where PDF was obtained")
    ingestion_source: str = Field(..., min_length=1, max_length=256, description="Identifier for the regulatory authority")
    file_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash of extracted text")
    file_size_bytes: int = Field(..., gt=0, description="Original PDF file size in bytes")
    page_count: int = Field(..., gt=0, description="Number of pages in PDF")
    extracted_text: str = Field(..., min_length=1, description="Full extracted text from PDF")
    extraction_confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction quality score")
    extraction_method: ExtractionMethod = Field(..., description="Method used for PDF text extraction")
    embeddings: List[EmbeddingData] = Field(..., min_length=1, description="List of chunk embeddings")
    metadata: Optional[DocumentMetadataInput] = Field(None, description="Optional document metadata")
    embedding_model: str = Field(default="models/embedding-001", max_length=128, description="Embedding model used")
    embedding_model_version: str = Field(default="001", max_length=64, description="Embedding model version")


class BatchUploadResponse(BaseModel):
    """Response after batch document upload"""
    document_id: UUID = Field(..., description="Created document ID")
    embeddings_count: int = Field(..., ge=0, description="Number of embeddings stored")
    total_tokens: int = Field(..., ge=0, description="Total tokens processed")
    processing_status: ProcessingStatus = Field(..., description="Current processing status")
    is_duplicate: bool = Field(..., description="Whether document was identified as duplicate")
    message: str = Field(..., description="Human-readable status message")
    created_at: datetime = Field(..., description="When document was created")


class BatchUploadMultipleRequest(BaseModel):
    """Request to upload multiple documents at once"""
    documents: List[BatchDocumentUpload] = Field(..., min_length=1, max_length=100, description="List of documents to upload")


class BatchUploadMultipleResponse(BaseModel):
    """Response after uploading multiple documents"""
    successful: int = Field(..., ge=0, description="Number of successfully uploaded documents")
    failed: int = Field(..., ge=0, description="Number of failed uploads")
    results: List[BatchUploadResponse] = Field(..., description="Results for each document")
    errors: List[str] = Field(default=[], description="Error messages for failed uploads")


class Error(BaseModel):
    """Standard error response schema"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    code: Optional[str] = Field(None, description="Error code for programmatic handling")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid request",
                "detail": "File size exceeds maximum allowed",
                "code": "FILE_TOO_LARGE"
            }
        }
