"""
SQLAlchemy ORM models for PDF Document Processing
Based on data-model.md specification
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class ProcessingStatus(str, PyEnum):
    """Document processing status states"""
    INGESTED = "ingested"
    PENDING_EMBEDDING = "pending_embedding"
    EMBEDDING_COMPLETE = "embedding_complete"
    EMBEDDING_FAILED = "embedding_failed"


class DocumentType(str, PyEnum):
    """Document classification types"""
    CIRCULAR = "circular"
    NOTICE = "notice"
    GUIDELINE = "guideline"
    POLICY = "policy"
    OTHER = "other"


class Language(str, PyEnum):
    """Primary document language"""
    ENGLISH = "english"
    CHINESE = "chinese"
    MULTILINGUAL = "multilingual"


class ExtractionMethod(str, PyEnum):
    """PDF extraction method used"""
    PDFPLUMBER = "pdfplumber"
    PYPDF_FALLBACK = "pypdf_fallback"
    MANUAL_UPLOAD = "manual_upload"


class ValidationStatus(str, PyEnum):
    """Metadata validation status"""
    VALIDATED = "validated"
    REQUIRES_REVIEW = "requires_review"
    VALIDATION_FAILED = "validation_failed"


class EventType(str, PyEnum):
    """Processing event types for audit trail"""
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


class EventStatus(str, PyEnum):
    """Processing event outcome status"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


class Document(Base):
    """
    Core entity representing a crawled MAS compliance PDF file
    """
    __tablename__ = "documents"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Source & Content
    source_url = Column(String(2048), nullable=False, unique=True, index=True)
    filename = Column(String(512), nullable=False)
    file_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)

    # Metadata
    ingestion_date = Column(DateTime(timezone=True), nullable=False, index=True)
    ingestion_source = Column(String(256), nullable=False)
    last_updated = Column(DateTime(timezone=True), nullable=True)
    processing_status = Column(
        Enum(ProcessingStatus),
        nullable=False,
        default=ProcessingStatus.INGESTED,
        index=True
    )

    # Quality Metrics
    extraction_confidence = Column(Float, nullable=False)  # 0.0-1.0
    is_duplicate = Column(Boolean, nullable=False, default=False)
    canonical_document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    document_metadata = relationship("DocumentMetadata", back_populates="document", uselist=False, cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="document", cascade="all, delete-orphan")
    processing_logs = relationship("ProcessingLog", back_populates="document", cascade="all, delete-orphan")
    canonical_document = relationship("Document", remote_side=[id])


class DocumentMetadata(Base):
    """
    Structured metadata extracted from document content or crawler headers
    """
    __tablename__ = "document_metadata"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, unique=True)

    # Content Classification
    document_type = Column(Enum(DocumentType), nullable=False)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    regulatory_framework = Column(ARRAY(String), nullable=False, default=[])

    # Language & Accessibility
    primary_language = Column(Enum(Language), nullable=False, default=Language.ENGLISH)
    has_chinese_content = Column(Boolean, nullable=False, default=False)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    ocr_required = Column(Boolean, nullable=False, default=False)

    # Source Attribution
    issuing_authority = Column(String(512), nullable=False)
    circular_number = Column(String(128), nullable=True)
    version = Column(String(64), nullable=False, default="1.0")

    # Processing Quality
    extraction_method = Column(Enum(ExtractionMethod), nullable=False, default=ExtractionMethod.PDFPLUMBER)
    validation_status = Column(Enum(ValidationStatus), nullable=False, default=ValidationStatus.REQUIRES_REVIEW)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="document_metadata")


class Embedding(Base):
    """
    Semantic vector embeddings for document search
    """
    __tablename__ = "embeddings"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)

    # Vector Data (768 dimensions for Gemini)
    embedding_vector = Column(Vector(768), nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    content_length = Column(Integer, nullable=False)

    # Metadata
    embedding_model = Column(String(128), nullable=False)
    embedding_model_version = Column(String(64), nullable=False)
    embedding_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Chunk Content
    chunk_text = Column(Text, nullable=False)
    chunk_start_page = Column(Integer, nullable=False, default=1)

    # Quality Tracking
    retry_count = Column(Integer, nullable=False, default=0)
    embedding_cost_usd = Column(Float, nullable=False, default=0.0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="embeddings")


class ProcessingLog(Base):
    """
    Immutable audit trail for all processing events
    """
    __tablename__ = "processing_logs"

    # Primary key
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)

    # Event Details
    event_type = Column(Enum(EventType), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    processor_version = Column(String(64), nullable=False)

    # Status & Outcome
    status = Column(Enum(EventStatus), nullable=False)
    error_message = Column(Text, nullable=True)

    # Embedding Event Details
    embedding_model = Column(String(128), nullable=True)
    embedding_model_version = Column(String(64), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    api_latency_ms = Column(Integer, nullable=True)
    retry_attempt = Column(Integer, nullable=True)
    retry_next_time = Column(DateTime(timezone=True), nullable=True)

    # Audit Context
    user_id = Column(String(128), nullable=True)
    api_endpoint = Column(String(256), nullable=True)

    # Timestamps (immutable)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="processing_logs")
