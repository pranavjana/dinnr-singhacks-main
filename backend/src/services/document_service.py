"""
Document service for CRUD operations and business logic.

This module provides:
- Document creation and deduplication checking
- Document retrieval and listing with filters
- Processing status updates
- Immutable audit trail logging
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models.document import (
    Document,
    DocumentMetadata,
    ProcessingLog,
    ProcessingStatus,
    EventType,
    EventStatus,
)
from ..models.schemas import DocumentDetail, DocumentMetadataResponse

logger = logging.getLogger(__name__)


class DocumentService:
    """Service class for document operations"""

    def __init__(self, db_session: Session):
        """
        Initialize document service with database session.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session

    def check_duplicate(self, file_hash: str) -> Optional[Document]:
        """
        Check if document with same content hash already exists.

        Implements content-based deduplication using SHA-256 hash.

        Args:
            file_hash: SHA-256 hash of extracted text content

        Returns:
            Existing Document if duplicate found, None otherwise
        """
        duplicate = self.db.query(Document).filter(
            Document.file_hash == file_hash
        ).first()

        if duplicate:
            logger.info(f"Duplicate document detected: {duplicate.id}, hash={file_hash[:16]}...")
            self.log_processing_event(
                document_id=duplicate.id,
                event_type=EventType.DEDUP_CHECK,
                status=EventStatus.SUCCESS,
                details={"is_duplicate": True, "file_hash": file_hash}
            )

        return duplicate

    def create_document(
        self,
        source_url: str,
        ingestion_source: str,
        filename: str,
        file_hash: str,
        file_size_bytes: int,
        page_count: int,
        extracted_text: str,
        extraction_confidence: float,
        extraction_method: str,
        is_duplicate: bool = False,
        canonical_document_id: Optional[UUID] = None
    ) -> Document:
        """
        Create a new document record in database.

        Args:
            source_url: Original URL where document was retrieved
            ingestion_source: Identifier for source system/authority
            filename: Original filename
            file_hash: SHA-256 hash of extracted text
            file_size_bytes: File size in bytes
            page_count: Number of pages
            extracted_text: Extracted text content
            extraction_confidence: Extraction quality score (0.0-1.0)
            extraction_method: Method used (pdfplumber/pypdf_fallback)
            is_duplicate: Whether this is a duplicate document
            canonical_document_id: ID of original document if duplicate

        Returns:
            Created Document instance
        """
        document = Document(
            source_url=source_url,
            ingestion_source=ingestion_source,
            filename=filename,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            extracted_text=extracted_text,
            extraction_confidence=extraction_confidence,
            ingestion_date=datetime.utcnow(),
            processing_status=ProcessingStatus.INGESTED,
            is_duplicate=is_duplicate,
            canonical_document_id=canonical_document_id,
            created_at=datetime.utcnow()
        )

        self.db.add(document)
        self.db.flush()  # Get document ID without committing

        # Log ingestion event
        self.log_processing_event(
            document_id=document.id,
            event_type=EventType.INGESTED,
            status=EventStatus.SUCCESS,
            details={
                "source_url": source_url,
                "extraction_method": extraction_method,
                "extraction_confidence": extraction_confidence
            }
        )

        logger.info(f"Document created: {document.id}, source={source_url}")

        return document

    def get_document(self, document_id: UUID) -> Optional[Document]:
        """
        Retrieve document by ID.

        Args:
            document_id: UUID of document

        Returns:
            Document instance if found, None otherwise
        """
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_document_by_source_url(self, source_url: str) -> Optional[Document]:
        """
        Retrieve document by source URL.

        Args:
            source_url: Original source URL

        Returns:
            Document instance if found, None otherwise
        """
        return self.db.query(Document).filter(Document.source_url == source_url).first()

    def list_documents(
        self,
        status: Optional[ProcessingStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Document]:
        """
        List documents with optional filtering.

        Args:
            status: Filter by processing status
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of Document instances
        """
        query = self.db.query(Document)

        if status:
            query = query.filter(Document.processing_status == status)

        documents = query.order_by(Document.created_at.desc()).limit(limit).offset(offset).all()

        logger.info(f"Listed {len(documents)} documents (status={status}, limit={limit}, offset={offset})")

        return documents

    def update_processing_status(
        self,
        document_id: UUID,
        new_status: ProcessingStatus,
        log_event: bool = True
    ) -> None:
        """
        Update document processing status.

        Args:
            document_id: UUID of document
            new_status: New processing status
            log_event: Whether to log status change event
        """
        document = self.get_document(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        old_status = document.processing_status
        document.processing_status = new_status
        document.last_updated = datetime.utcnow()

        self.db.flush()

        if log_event:
            # Map status to event type
            event_type_map = {
                ProcessingStatus.PENDING_EMBEDDING: EventType.EMBEDDING_QUEUED,
                ProcessingStatus.EMBEDDING_COMPLETE: EventType.EMBEDDING_COMPLETED,
                ProcessingStatus.EMBEDDING_FAILED: EventType.EMBEDDING_FAILED
            }

            event_type = event_type_map.get(new_status, EventType.EXTRACTION_COMPLETED)

            self.log_processing_event(
                document_id=document_id,
                event_type=event_type,
                status=EventStatus.SUCCESS if "COMPLETE" in new_status.value else EventStatus.PARTIAL_SUCCESS,
                details={"old_status": old_status.value, "new_status": new_status.value}
            )

        logger.info(f"Updated document {document_id} status: {old_status.value} → {new_status.value}")

    def log_processing_event(
        self,
        document_id: UUID,
        event_type: EventType,
        status: EventStatus,
        details: Optional[dict] = None,
        error_message: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_model_version: Optional[str] = None,
        tokens_used: Optional[int] = None,
        api_latency_ms: Optional[int] = None,
        retry_attempt: Optional[int] = None,
        retry_next_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        api_endpoint: Optional[str] = None
    ) -> ProcessingLog:
        """
        Create immutable audit trail log entry.

        This is an append-only operation - logs cannot be updated or deleted.

        Args:
            document_id: UUID of document
            event_type: Type of processing event
            status: Event outcome status
            details: Additional event details (will be logged but not stored in DB)
            error_message: Error message if event failed
            embedding_model: Embedding model name if applicable
            embedding_model_version: Embedding model version
            tokens_used: API tokens consumed
            api_latency_ms: API call latency
            retry_attempt: Retry attempt number (1-3)
            retry_next_time: Scheduled next retry time
            user_id: User who triggered event
            api_endpoint: API endpoint that triggered event

        Returns:
            Created ProcessingLog instance
        """
        log_entry = ProcessingLog(
            document_id=document_id,
            event_type=event_type,
            timestamp=datetime.utcnow(),
            processor_version="1.0.0",  # TODO: Get from config
            status=status,
            error_message=error_message,
            embedding_model=embedding_model,
            embedding_model_version=embedding_model_version,
            tokens_used=tokens_used,
            api_latency_ms=api_latency_ms,
            retry_attempt=retry_attempt,
            retry_next_time=retry_next_time,
            user_id=user_id,
            api_endpoint=api_endpoint,
            created_at=datetime.utcnow()
        )

        self.db.add(log_entry)
        self.db.flush()

        logger.info(
            f"Logged processing event: document={document_id}, "
            f"event={event_type.value}, status={status.value}, "
            f"details={details}"
        )

        return log_entry

    def get_audit_trail(
        self,
        document_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[ProcessingLog], int]:
        """
        Retrieve audit trail for a document.

        Returns logs in reverse chronological order (most recent first).

        Args:
            document_id: UUID of document
            limit: Maximum number of log entries
            offset: Pagination offset

        Returns:
            Tuple of (log_entries, total_count)
        """
        query = self.db.query(ProcessingLog).filter(
            ProcessingLog.document_id == document_id
        )

        total_count = query.count()

        logs = query.order_by(ProcessingLog.timestamp.desc()).limit(limit).offset(offset).all()

        logger.info(f"Retrieved {len(logs)} audit log entries for document {document_id}")

        return logs, total_count

    def get_documents_pending_embedding(self, limit: int = 100) -> List[Document]:
        """
        Get documents that are pending embedding.

        Used by retry queue to identify documents ready for embedding retry.

        Args:
            limit: Maximum number of documents to return

        Returns:
            List of Document instances with status PENDING_EMBEDDING
        """
        documents = self.db.query(Document).filter(
            Document.processing_status == ProcessingStatus.PENDING_EMBEDDING
        ).limit(limit).all()

        return documents

    def get_documents_for_annual_refresh(
        self,
        batch_size: int = 100
    ) -> List[Document]:
        """
        Get documents for annual refresh cycle.

        Returns documents that should be re-embedded and validated.

        Args:
            batch_size: Number of documents to return

        Returns:
            List of Document instances
        """
        documents = self.db.query(Document).filter(
            or_(
                Document.processing_status == ProcessingStatus.EMBEDDING_COMPLETE,
                Document.processing_status == ProcessingStatus.EMBEDDING_FAILED
            )
        ).limit(batch_size).all()

        logger.info(f"Retrieved {len(documents)} documents for annual refresh")

        return documents

    def commit(self):
        """Commit current database transaction"""
        self.db.commit()

    def rollback(self):
        """Rollback current database transaction"""
        self.db.rollback()
