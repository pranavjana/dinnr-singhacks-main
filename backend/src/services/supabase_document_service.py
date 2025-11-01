"""
Document service using Supabase REST API (no direct PostgreSQL connection).

This service uses HTTP POST/GET requests to interact with Supabase instead of
direct database connections, which works around IPv4 connection issues.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from supabase import create_client, Client

from config import settings
from ..models.schemas import IngestedDocumentResponse, ProcessingStatus

logger = logging.getLogger(__name__)


class SupabaseDocumentService:
    """Service class for document operations using Supabase REST API"""

    def __init__(self):
        """Initialize Supabase client"""
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        logger.info("Supabase client initialized")

    def check_duplicate(self, file_hash: str) -> Optional[dict]:
        """
        Check if document with same content hash already exists.

        Args:
            file_hash: SHA-256 hash of extracted text content

        Returns:
            Existing document dict if duplicate found, None otherwise
        """
        try:
            response = self.supabase.table('documents').select('*').eq('file_hash', file_hash).execute()

            if response.data and len(response.data) > 0:
                duplicate = response.data[0]
                logger.info(f"Duplicate document detected: {duplicate['id']}, hash={file_hash[:16]}...")

                # Log dedup check event
                self.log_processing_event(
                    document_id=duplicate['id'],
                    event_type='dedup_check',
                    status='success',
                    processor_version='1.0.0'
                )

                return duplicate

            return None

        except Exception as e:
            logger.error(f"Error checking duplicate: {str(e)}")
            return None

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
        canonical_document_id: Optional[str] = None
    ) -> dict:
        """
        Create a new document record using Supabase REST API.

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
            Created document dict
        """
        document_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        document_data = {
            'id': document_id,
            'source_url': source_url,
            'ingestion_source': ingestion_source,
            'filename': filename,
            'file_hash': file_hash,
            'file_size_bytes': file_size_bytes,
            'page_count': page_count,
            'extracted_text': extracted_text,
            'extraction_confidence': extraction_confidence,
            'ingestion_date': now,
            'processing_status': 'ingested',
            'is_duplicate': is_duplicate,
            'canonical_document_id': canonical_document_id,
            'created_at': now
        }

        try:
            response = self.supabase.table('documents').insert(document_data).execute()

            if not response.data:
                raise Exception("Failed to create document - no data returned")

            created_doc = response.data[0]

            # Log ingestion event
            self.log_processing_event(
                document_id=document_id,
                event_type='ingested',
                status='success',
                processor_version='1.0.0'
            )

            logger.info(f"Document created: {document_id}, source={source_url}")

            return created_doc

        except Exception as e:
            logger.error(f"Failed to create document: {str(e)}")
            raise

    def update_processing_status(
        self,
        document_id: str,
        new_status: str,
        log_event: bool = True
    ) -> None:
        """
        Update document processing status.

        Args:
            document_id: UUID of document
            new_status: New processing status
            log_event: Whether to log status change event
        """
        try:
            now = datetime.utcnow().isoformat()

            response = self.supabase.table('documents').update({
                'processing_status': new_status,
                'last_updated': now
            }).eq('id', document_id).execute()

            if log_event:
                # Map status to event type
                event_type_map = {
                    'pending_embedding': 'embedding_queued',
                    'embedding_complete': 'embedding_completed',
                    'embedding_failed': 'embedding_failed'
                }

                event_type = event_type_map.get(new_status, 'extraction_completed')

                self.log_processing_event(
                    document_id=document_id,
                    event_type=event_type,
                    status='success' if 'complete' in new_status else 'partial_success',
                    processor_version='1.0.0'
                )

            logger.info(f"Updated document {document_id} status to: {new_status}")

        except Exception as e:
            logger.error(f"Failed to update status: {str(e)}")
            raise

    def log_processing_event(
        self,
        document_id: str,
        event_type: str,
        status: str,
        processor_version: str = '1.0.0',
        error_message: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_model_version: Optional[str] = None,
        tokens_used: Optional[int] = None,
        api_latency_ms: Optional[int] = None,
        retry_attempt: Optional[int] = None,
        retry_next_time: Optional[str] = None,
        user_id: Optional[str] = None,
        api_endpoint: Optional[str] = None
    ) -> dict:
        """
        Create immutable audit trail log entry using Supabase REST API.

        Args:
            document_id: UUID of document
            event_type: Type of processing event
            status: Event outcome status
            processor_version: Version of processor
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
            Created processing log dict
        """
        log_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        log_data = {
            'id': log_id,
            'document_id': document_id,
            'event_type': event_type,
            'timestamp': now,
            'processor_version': processor_version,
            'status': status,
            'error_message': error_message,
            'embedding_model': embedding_model,
            'embedding_model_version': embedding_model_version,
            'tokens_used': tokens_used,
            'api_latency_ms': api_latency_ms,
            'retry_attempt': retry_attempt,
            'retry_next_time': retry_next_time,
            'user_id': user_id,
            'api_endpoint': api_endpoint,
            'created_at': now
        }

        try:
            response = self.supabase.table('processing_logs').insert(log_data).execute()

            if response.data:
                logger.info(
                    f"Logged processing event: document={document_id}, "
                    f"event={event_type}, status={status}"
                )
                return response.data[0]
            else:
                logger.warning(f"Log entry created but no data returned for document {document_id}")
                return log_data

        except Exception as e:
            logger.error(f"Failed to log processing event: {str(e)}")
            # Don't raise - logging should not block the main process
            return log_data

    def create_document_with_embeddings(
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
        canonical_document_id: Optional[str] = None,
        embeddings_data: Optional[list] = None,
        total_tokens: int = 0
    ) -> dict:
        """
        Create a new document with pre-computed embeddings.

        This method uploads document + embeddings in a single batch.

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
            embeddings_data: List of embedding dicts with chunk data
            total_tokens: Total tokens processed

        Returns:
            Created document dict
        """
        document_id = str(uuid4())
        now = datetime.utcnow().isoformat()

        # Determine processing status based on whether embeddings were provided
        processing_status = 'embedding_complete' if embeddings_data else 'pending_embedding'

        document_data = {
            'id': document_id,
            'source_url': source_url,
            'ingestion_source': ingestion_source,
            'filename': filename,
            'file_hash': file_hash,
            'file_size_bytes': file_size_bytes,
            'page_count': page_count,
            'extracted_text': extracted_text,
            'extraction_confidence': extraction_confidence,
            'ingestion_date': now,
            'processing_status': processing_status,
            'is_duplicate': is_duplicate,
            'canonical_document_id': canonical_document_id,
            'created_at': now
        }

        try:
            # Create document
            response = self.supabase.table('documents').insert(document_data).execute()

            if not response.data:
                raise Exception("Failed to create document - no data returned")

            created_doc = response.data[0]

            # Log ingestion event
            self.log_processing_event(
                document_id=document_id,
                event_type='ingested',
                status='success',
                processor_version='1.0.0'
            )

            # Create embeddings if provided
            if embeddings_data and len(embeddings_data) > 0:
                self._create_embeddings_batch(
                    document_id=document_id,
                    embeddings_data=embeddings_data
                )

                # Log embedding completion
                avg_latency = sum(e.get('api_latency_ms', 0) for e in embeddings_data) // len(embeddings_data)
                self.log_processing_event(
                    document_id=document_id,
                    event_type='embedding_completed',
                    status='success',
                    processor_version='1.0.0',
                    embedding_model='models/embedding-001',
                    embedding_model_version='001',
                    tokens_used=total_tokens,
                    api_latency_ms=avg_latency
                )

                logger.info(
                    f"Document created with {len(embeddings_data)} embeddings: "
                    f"{document_id}, {total_tokens} tokens"
                )
            else:
                # Log that document is pending embedding
                self.log_processing_event(
                    document_id=document_id,
                    event_type='embedding_queued',
                    status='success',
                    processor_version='1.0.0'
                )

                logger.info(f"Document created (pending embedding): {document_id}")

            return created_doc

        except Exception as e:
            logger.error(f"Failed to create document with embeddings: {str(e)}")
            raise

    def _create_embeddings_batch(
        self,
        document_id: str,
        embeddings_data: list
    ) -> None:
        """
        Bulk create embeddings for a document.

        Args:
            document_id: UUID of parent document
            embeddings_data: List of embedding dicts
        """
        if not embeddings_data:
            return

        now = datetime.utcnow().isoformat()
        embedding_records = []

        for emb in embeddings_data:
            embedding_record = {
                'id': str(uuid4()),
                'document_id': document_id,
                'embedding_vector': emb['embedding_vector'],
                'chunk_index': emb['chunk_index'],
                'content_length': emb['content_length'],
                'embedding_model': 'models/embedding-001',
                'embedding_model_version': '001',
                'embedding_timestamp': now,
                'chunk_text': emb['chunk_text'],
                'chunk_start_page': emb.get('chunk_start_page', 1),
                'retry_count': 0,
                'embedding_cost_usd': 0.0,  # Free tier
                'created_at': now
            }
            embedding_records.append(embedding_record)

        try:
            # Bulk insert embeddings
            response = self.supabase.table('embeddings').insert(embedding_records).execute()

            if response.data:
                logger.info(f"Created {len(embedding_records)} embeddings for document {document_id}")
            else:
                logger.warning(f"Embeddings created but no data returned for document {document_id}")

        except Exception as e:
            logger.error(f"Failed to create embeddings batch: {str(e)}")
            raise

    def get_document(self, document_id: str) -> Optional[dict]:
        """
        Retrieve document by ID.

        Args:
            document_id: UUID of document

        Returns:
            Document dict if found, None otherwise
        """
        try:
            response = self.supabase.table('documents').select('*').eq('id', document_id).execute()

            if response.data and len(response.data) > 0:
                return response.data[0]

            return None

        except Exception as e:
            logger.error(f"Failed to get document: {str(e)}")
            return None
