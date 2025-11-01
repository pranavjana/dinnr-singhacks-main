"""
Gemini Embedding Service for document semantic vectorization.

This module provides integration with Google's Gemini embedding-001 model
to generate 768-dimensional semantic embeddings for text chunks.

Key Features:
- Batch embedding generation with rate limiting
- Retry logic with exponential backoff
- Cost tracking and token usage monitoring
- Error handling and logging
"""

import logging
import time
from typing import List, Optional, Tuple
from dataclasses import dataclass

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """
    Result of embedding generation for a single text chunk.

    Attributes:
        embedding: 768-dimensional vector (list of floats)
        token_count: Number of tokens processed
        api_latency_ms: API call latency in milliseconds
        success: Whether embedding generation succeeded
        error_message: Error message if failed
    """
    embedding: Optional[List[float]]
    token_count: int
    api_latency_ms: int
    success: bool
    error_message: Optional[str] = None


class GeminiEmbeddingService:
    """
    Service for generating embeddings using Google Gemini API.

    This service handles:
    - API client initialization and configuration
    - Single and batch embedding generation
    - Rate limiting and retry logic
    - Error handling and monitoring
    """

    # Model configuration
    MODEL_NAME = "models/embedding-001"
    EMBEDDING_DIMENSION = 768
    TASK_TYPE = "RETRIEVAL_DOCUMENT"  # For document embedding

    # Rate limiting (Gemini free tier: 1500 requests/day)
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds
    RETRY_BACKOFF_MULTIPLIER = 2.0
    MAX_RETRY_DELAY = 60.0  # seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: int = 30
    ):
        """
        Initialize Gemini embedding service.

        Args:
            api_key: Google API key (defaults to settings.GOOGLE_API_KEY)
            timeout_seconds: API request timeout in seconds

        Raises:
            ValueError: If API key is not provided or invalid
        """
        self.api_key = api_key or settings.GOOGLE_API_KEY
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise ValueError("Google API key is required")

        # Configure Gemini API
        genai.configure(api_key=self.api_key)

        # Get model configuration
        try:
            self.model_info = genai.get_model(self.MODEL_NAME)
            self.model_version = self._extract_model_version()
            logger.info(
                f"Gemini embedding service initialized: "
                f"model={self.MODEL_NAME}, version={self.model_version}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise

    def _extract_model_version(self) -> str:
        """
        Extract model version from model info.

        Returns:
            Model version string (e.g., "001")
        """
        # Extract version from model name (e.g., "models/embedding-001" -> "001")
        parts = self.MODEL_NAME.split("-")
        if len(parts) >= 2:
            return parts[-1]
        return "unknown"

    def generate_embedding(
        self,
        text: str,
        task_type: str = TASK_TYPE
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text chunk.

        Args:
            text: Input text to embed
            task_type: Task type for embedding (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)

        Returns:
            EmbeddingResult with embedding vector or error
        """
        if not text or not text.strip():
            return EmbeddingResult(
                embedding=None,
                token_count=0,
                api_latency_ms=0,
                success=False,
                error_message="Empty or whitespace-only text"
            )

        # Try embedding generation with retry logic
        for attempt in range(self.MAX_RETRIES):
            try:
                start_time = time.time()

                # Generate embedding using Gemini API
                result = genai.embed_content(
                    model=self.MODEL_NAME,
                    content=text,
                    task_type=task_type
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Extract embedding vector
                embedding = result.get('embedding', None)

                if not embedding:
                    logger.error("No embedding returned from Gemini API")
                    return EmbeddingResult(
                        embedding=None,
                        token_count=0,
                        api_latency_ms=latency_ms,
                        success=False,
                        error_message="No embedding in API response"
                    )

                # Validate embedding dimension
                if len(embedding) != self.EMBEDDING_DIMENSION:
                    logger.error(
                        f"Unexpected embedding dimension: {len(embedding)} "
                        f"(expected {self.EMBEDDING_DIMENSION})"
                    )
                    return EmbeddingResult(
                        embedding=None,
                        token_count=0,
                        api_latency_ms=latency_ms,
                        success=False,
                        error_message=f"Invalid embedding dimension: {len(embedding)}"
                    )

                # Estimate token count (rough approximation: 1 token ≈ 4 chars)
                token_count = len(text) // 4

                logger.debug(
                    f"Generated embedding: {len(text)} chars, "
                    f"{token_count} tokens, {latency_ms}ms latency"
                )

                return EmbeddingResult(
                    embedding=embedding,
                    token_count=token_count,
                    api_latency_ms=latency_ms,
                    success=True
                )

            except google_exceptions.ResourceExhausted as e:
                # Rate limit exceeded
                retry_delay = self._calculate_retry_delay(attempt)
                logger.warning(
                    f"Rate limit exceeded (attempt {attempt + 1}/{self.MAX_RETRIES}), "
                    f"retrying in {retry_delay}s: {e}"
                )

                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return EmbeddingResult(
                        embedding=None,
                        token_count=0,
                        api_latency_ms=0,
                        success=False,
                        error_message=f"Rate limit exceeded after {self.MAX_RETRIES} retries"
                    )

            except google_exceptions.InvalidArgument as e:
                # Invalid request (don't retry)
                logger.error(f"Invalid request to Gemini API: {e}")
                return EmbeddingResult(
                    embedding=None,
                    token_count=0,
                    api_latency_ms=0,
                    success=False,
                    error_message=f"Invalid request: {str(e)}"
                )

            except Exception as e:
                # Unexpected error
                retry_delay = self._calculate_retry_delay(attempt)
                logger.error(
                    f"Unexpected error generating embedding "
                    f"(attempt {attempt + 1}/{self.MAX_RETRIES}): {e}"
                )

                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    return EmbeddingResult(
                        embedding=None,
                        token_count=0,
                        api_latency_ms=0,
                        success=False,
                        error_message=f"Failed after {self.MAX_RETRIES} retries: {str(e)}"
                    )

    def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = TASK_TYPE,
        batch_size: int = 100
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for a batch of text chunks using Gemini's batch API.

        The Gemini API supports batching multiple texts in a single request,
        which is much faster than sequential processing.

        Args:
            texts: List of text chunks to embed
            task_type: Task type for embedding
            batch_size: Number of texts to process in each API call (max 100)

        Returns:
            List of EmbeddingResult objects (one per input text)
        """
        if not texts:
            logger.warning("Empty text list provided to generate_embeddings_batch")
            return []

        results = []
        total_texts = len(texts)

        logger.info(f"Starting batch embedding generation for {total_texts} texts (batch_size={batch_size})")

        # Process in batches of batch_size
        for batch_start in range(0, total_texts, batch_size):
            batch_end = min(batch_start + batch_size, total_texts)
            batch_texts = texts[batch_start:batch_end]

            # Try batch embedding with retry logic
            for attempt in range(self.MAX_RETRIES):
                try:
                    start_time = time.time()

                    # Use batch_embed_contents for multiple texts at once
                    result = genai.embed_content(
                        model=self.MODEL_NAME,
                        content=batch_texts,
                        task_type=task_type
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    # Extract embeddings
                    embeddings = result.get('embedding', [])

                    if not embeddings:
                        logger.error("No embeddings returned from batch API")
                        # Fall back to sequential processing for this batch
                        for text in batch_texts:
                            results.append(self.generate_embedding(text, task_type))
                        break

                    # Create EmbeddingResult for each text in batch
                    for i, (text, embedding) in enumerate(zip(batch_texts, embeddings)):
                        token_count = len(text) // 4  # Rough approximation

                        results.append(EmbeddingResult(
                            embedding=embedding,
                            token_count=token_count,
                            api_latency_ms=latency_ms // len(batch_texts),  # Distribute latency
                            success=True
                        ))

                    logger.info(
                        f"Progress: {batch_end}/{total_texts} embeddings generated "
                        f"(batch {batch_start//batch_size + 1})"
                    )
                    break  # Success, exit retry loop

                except google_exceptions.ResourceExhausted as e:
                    retry_delay = self._calculate_retry_delay(attempt)
                    logger.warning(
                        f"Rate limit exceeded for batch {batch_start}-{batch_end} "
                        f"(attempt {attempt + 1}/{self.MAX_RETRIES}), retrying in {retry_delay}s"
                    )

                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        # Fall back to sequential processing for this batch
                        logger.error(f"Batch API failed after {self.MAX_RETRIES} retries, falling back to sequential")
                        for text in batch_texts:
                            results.append(self.generate_embedding(text, task_type))
                        break

                except Exception as e:
                    logger.error(f"Unexpected error in batch embedding: {e}")
                    # Fall back to sequential processing for this batch
                    for text in batch_texts:
                        results.append(self.generate_embedding(text, task_type))
                    break

        # Log batch summary
        successful = sum(1 for r in results if r.success)
        failed = total_texts - successful
        total_tokens = sum(r.token_count for r in results if r.success)
        avg_latency = (
            sum(r.api_latency_ms for r in results if r.success) / successful
            if successful > 0 else 0
        )

        logger.info(
            f"Batch embedding completed: {successful} successful, {failed} failed, "
            f"{total_tokens} total tokens, {avg_latency:.1f}ms avg latency"
        )

        return results

    def _calculate_retry_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for retry.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.INITIAL_RETRY_DELAY * (
            self.RETRY_BACKOFF_MULTIPLIER ** attempt
        )
        return min(delay, self.MAX_RETRY_DELAY)

    def generate_query_embedding(self, query: str) -> EmbeddingResult:
        """
        Generate embedding for a search query.

        Uses RETRIEVAL_QUERY task type for query embedding.

        Args:
            query: Search query text

        Returns:
            EmbeddingResult with query embedding
        """
        return self.generate_embedding(
            text=query,
            task_type="RETRIEVAL_QUERY"
        )

    def get_model_info(self) -> dict:
        """
        Get information about the embedding model.

        Returns:
            Dictionary with model metadata
        """
        return {
            "model_name": self.MODEL_NAME,
            "model_version": self.model_version,
            "embedding_dimension": self.EMBEDDING_DIMENSION,
            "task_type": self.TASK_TYPE
        }


# Global singleton instance (lazy initialization)
_embedding_service: Optional[GeminiEmbeddingService] = None


def get_embedding_service() -> GeminiEmbeddingService:
    """
    Get or create global embedding service instance.

    Returns:
        Singleton GeminiEmbeddingService instance
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = GeminiEmbeddingService()
        logger.info("Created global Gemini embedding service instance")

    return _embedding_service
