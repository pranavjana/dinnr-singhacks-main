"""
PDF processor that integrates crawler downloads with database storage.

This module processes downloaded PDFs by:
1. Extracting text from the PDF file
2. Checking for duplicates
3. Storing document metadata in database
4. Queueing for embedding (if not duplicate)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .pdf_extraction import extract_pdf_content, InvalidPDFError, PDFExtractionError
from .document_service import DocumentService
from ..models.document import ProcessingStatus, EventType, EventStatus
from ..models.schemas import IngestedDocumentResponse

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Process downloaded PDFs and store in database"""

    def __init__(self, db_session: Session):
        """
        Initialize PDF processor.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.doc_service = DocumentService(db_session)

    def process_downloaded_pdf(
        self,
        pdf_path: str,
        source_url: str,
        ingestion_source: str = "MAS",
        document_title: Optional[str] = None
    ) -> IngestedDocumentResponse:
        """
        Process a downloaded PDF file and store in database.

        Workflow:
        1. Extract text from PDF using pdfplumber/pypdf
        2. Check for duplicate based on content hash
        3. Create Document record in database
        4. Log processing events for audit trail
        5. Return ingestion response

        Args:
            pdf_path: Absolute path to downloaded PDF file
            source_url: Original URL where PDF was retrieved
            ingestion_source: Source system identifier (e.g., "MAS", "CBR")
            document_title: Optional document title for metadata

        Returns:
            IngestedDocumentResponse with document ID and status

        Raises:
            InvalidPDFError: If PDF signature validation fails
            PDFExtractionError: If text extraction fails
            ValueError: If required parameters missing
        """
        if not pdf_path or not source_url:
            raise ValueError("pdf_path and source_url are required")

        logger.info(f"Processing PDF: {pdf_path} from {source_url}")

        # Read PDF file bytes
        with open(pdf_path, 'rb') as f:
            file_bytes = f.read()

        file_size_bytes = len(file_bytes)

        # Extract text and metadata from PDF
        try:
            extracted_text, page_count, confidence, method, file_hash = extract_pdf_content(file_bytes)

            logger.info(
                f"PDF extraction successful: pages={page_count}, "
                f"confidence={confidence}, method={method}, hash={file_hash[:16]}..."
            )

        except InvalidPDFError as e:
            logger.error(f"Invalid PDF signature: {pdf_path}, error={str(e)}")
            raise

        except PDFExtractionError as e:
            logger.error(f"PDF extraction failed: {pdf_path}, error={str(e)}")
            raise

        # Check for duplicate document
        duplicate_doc = self.doc_service.check_duplicate(file_hash)

        if duplicate_doc:
            logger.warning(
                f"Duplicate document detected: {file_hash[:16]}... "
                f"matches existing document {duplicate_doc.id}"
            )

            # Still create a record, but mark as duplicate
            document = self.doc_service.create_document(
                source_url=source_url,
                ingestion_source=ingestion_source,
                filename=Path(pdf_path).name,
                file_hash=file_hash,
                file_size_bytes=file_size_bytes,
                page_count=page_count,
                extracted_text=extracted_text,
                extraction_confidence=confidence,
                extraction_method=method,
                is_duplicate=True,
                canonical_document_id=duplicate_doc.id
            )

            self.db.commit()

            return IngestedDocumentResponse(
                document_id=document.id,
                status=ProcessingStatus.INGESTED,
                ingestion_date=document.ingestion_date,
                message=f"Duplicate document (canonical: {duplicate_doc.id}). Not queued for embedding."
            )

        # Create new document (not a duplicate)
        document = self.doc_service.create_document(
            source_url=source_url,
            ingestion_source=ingestion_source,
            filename=Path(pdf_path).name,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            extracted_text=extracted_text,
            extraction_confidence=confidence,
            extraction_method=method,
            is_duplicate=False
        )

        # Log extraction completion
        self.doc_service.log_processing_event(
            document_id=document.id,
            event_type=EventType.EXTRACTION_COMPLETED,
            status=EventStatus.SUCCESS,
            details={
                "extraction_method": method,
                "extraction_confidence": confidence,
                "page_count": page_count
            }
        )

        # Update status to pending embedding
        self.doc_service.update_processing_status(
            document_id=document.id,
            new_status=ProcessingStatus.PENDING_EMBEDDING,
            log_event=True
        )

        self.db.commit()

        logger.info(
            f"Document ingested successfully: {document.id}, "
            f"status={document.processing_status.value}"
        )

        return IngestedDocumentResponse(
            document_id=document.id,
            status=document.processing_status,
            ingestion_date=document.ingestion_date,
            message="Document queued for embedding. Will be searchable shortly."
        )

    def process_directory(
        self,
        download_dir: str,
        ingestion_source: str = "MAS",
        pattern: str = "*.pdf"
    ) -> list[IngestedDocumentResponse]:
        """
        Process all PDF files in a directory.

        Useful for batch processing existing downloads.

        Args:
            download_dir: Directory containing downloaded PDFs
            ingestion_source: Source system identifier
            pattern: File pattern to match (default: *.pdf)

        Returns:
            List of IngestedDocumentResponse for each processed PDF
        """
        download_path = Path(download_dir)

        if not download_path.exists():
            raise ValueError(f"Download directory does not exist: {download_dir}")

        pdf_files = list(download_path.glob(pattern))

        logger.info(f"Found {len(pdf_files)} PDF files in {download_dir}")

        results = []

        for pdf_file in pdf_files:
            try:
                # Use filename as source URL if not available
                # (In real workflow, crawler should provide actual source URL)
                source_url = f"file://{pdf_file.absolute()}"

                response = self.process_downloaded_pdf(
                    pdf_path=str(pdf_file.absolute()),
                    source_url=source_url,
                    ingestion_source=ingestion_source
                )

                results.append(response)

                logger.info(f"Processed {pdf_file.name}: {response.document_id}")

            except Exception as e:
                logger.error(f"Failed to process {pdf_file.name}: {str(e)}")
                # Continue processing other files
                continue

        logger.info(f"Batch processing complete: {len(results)}/{len(pdf_files)} successful")

        return results
