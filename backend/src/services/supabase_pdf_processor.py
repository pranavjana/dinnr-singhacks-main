"""
PDF processor that uses Supabase REST API instead of direct database connection.

This module processes downloaded PDFs by:
1. Extracting text from the PDF file
2. Chunking the extracted text
3. Generating embeddings for each chunk using Gemini
4. Checking for duplicates via Supabase API
5. Storing document metadata + embeddings via Supabase API
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .pdf_extraction import extract_pdf_content, InvalidPDFError, PDFExtractionError
from .supabase_document_service import SupabaseDocumentService
from .text_chunker import TextChunker
from .gemini_embedding_service import get_embedding_service
from ..models.schemas import IngestedDocumentResponse, ProcessingStatus

logger = logging.getLogger(__name__)


class SupabasePDFProcessor:
    """Process downloaded PDFs and store in Supabase via REST API"""

    # Chunk configuration (optimized for Gemini embedding-001)
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_OVERLAP = 200

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        enable_embedding: bool = True
    ):
        """
        Initialize PDF processor with Supabase service.

        Args:
            chunk_size: Text chunk size in characters
            overlap: Overlap between chunks
            enable_embedding: Whether to generate embeddings (set False to skip)
        """
        self.doc_service = SupabaseDocumentService()
        self.enable_embedding = enable_embedding

        if self.enable_embedding:
            self.chunker = TextChunker(
                chunk_size=chunk_size,
                overlap=overlap,
                respect_sentence_boundaries=True
            )
            self.embedding_service = get_embedding_service()
            logger.info(f"PDF processor initialized with embedding enabled (chunk_size={chunk_size}, overlap={overlap})")
        else:
            logger.info("PDF processor initialized with embedding disabled")

    def process_downloaded_pdf(
        self,
        pdf_path: str,
        source_url: str,
        ingestion_source: str = "MAS",
        document_title: Optional[str] = None
    ) -> IngestedDocumentResponse:
        """
        Process a downloaded PDF file and store in Supabase.

        Workflow:
        1. Extract text from PDF using pdfplumber/pypdf
        2. Check for duplicate based on content hash
        3. Create Document record via Supabase API
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
                f"matches existing document {duplicate_doc['id']}"
            )

            # Return existing document info without creating a new record
            return IngestedDocumentResponse(
                document_id=duplicate_doc['id'],
                status=ProcessingStatus(duplicate_doc.get('processing_status', 'ingested')),
                ingestion_date=duplicate_doc.get('ingestion_date', datetime.utcnow().isoformat()),
                message=f"Duplicate document (already exists: {duplicate_doc['id']}). Skipped."
            )

        # Generate embeddings locally if enabled
        embeddings_data = None
        total_tokens = 0

        if self.enable_embedding:
            logger.info("Generating embeddings locally...")

            try:
                # Chunk the text
                chunks = self.chunker.chunk_text(extracted_text)
                logger.info(f"Text chunked into {len(chunks)} chunks")

                # Extract chunk texts for batch processing
                chunk_texts = [chunk.text for chunk in chunks]

                # Generate embeddings in batch (much faster!)
                results = self.embedding_service.generate_embeddings_batch(
                    texts=chunk_texts,
                    batch_size=100  # Process 100 chunks per API call
                )

                # Check if any embeddings failed
                failed_chunks = [i for i, r in enumerate(results) if not r.success]
                if failed_chunks:
                    error_msg = f"Embedding generation failed for {len(failed_chunks)} chunks"
                    logger.error(error_msg)
                    raise Exception(error_msg)

                # Combine chunk metadata with embedding results
                embeddings_data = []
                for chunk, result in zip(chunks, results):
                    embeddings_data.append({
                        'chunk_index': chunk.chunk_index,
                        'chunk_text': chunk.text,
                        'content_length': chunk.content_length,
                        'embedding_vector': result.embedding,
                        'chunk_start_page': 1,  # TODO: Track actual page if needed
                        'token_count': result.token_count,
                        'api_latency_ms': result.api_latency_ms
                    })

                    total_tokens += result.token_count

                logger.info(f"Generated {len(embeddings_data)} embeddings: {total_tokens} tokens total")

            except Exception as e:
                logger.error(f"Embedding generation failed: {str(e)}")
                # Fall back to creating document without embeddings
                embeddings_data = None

        # Create new document (not a duplicate)
        document = self.doc_service.create_document_with_embeddings(
            source_url=source_url,
            ingestion_source=ingestion_source,
            filename=Path(pdf_path).name,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            extracted_text=extracted_text,
            extraction_confidence=confidence,
            extraction_method=method,
            is_duplicate=False,
            embeddings_data=embeddings_data,
            total_tokens=total_tokens
        )

        status = ProcessingStatus.EMBEDDING_COMPLETE if embeddings_data else ProcessingStatus.PENDING_EMBEDDING
        message = (
            f"Document processed successfully with {len(embeddings_data)} embeddings ({total_tokens} tokens)"
            if embeddings_data else
            "Document queued for embedding. Will be searchable shortly."
        )

        logger.info(f"Document ingested successfully: {document['id']}, status={status.value}")

        return IngestedDocumentResponse(
            document_id=document['id'],
            status=status,
            ingestion_date=document['ingestion_date'],
            message=message
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
                source_url = f"https://www.mas.gov.sg/{pdf_file.name}"

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
