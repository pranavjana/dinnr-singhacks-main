"""
Text chunking utility for document embedding.

This module provides text chunking functionality with overlapping windows
to ensure semantic coherence across chunk boundaries. It is designed to work
with the Google Gemini embedding-001 model.

Key Features:
- Configurable chunk size and overlap
- Preserves semantic boundaries (sentences/paragraphs)
- Metadata tracking for each chunk
- Handles edge cases (empty text, short documents)
"""

import logging
import re
from typing import List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """
    Represents a text chunk with metadata.

    Attributes:
        text: The chunk text content
        chunk_index: Zero-based index of the chunk
        start_char: Starting character position in original text
        end_char: Ending character position in original text
        content_length: Length of chunk text in characters
    """
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    content_length: int


class TextChunker:
    """
    Splits text into overlapping chunks for embedding generation.

    The chunker uses a sliding window approach with configurable chunk size
    and overlap. It attempts to split at sentence boundaries to maintain
    semantic coherence.
    """

    # Default values optimized for Gemini embedding-001
    DEFAULT_CHUNK_SIZE = 1000  # characters
    DEFAULT_OVERLAP = 200  # characters

    # Sentence boundary pattern (simplified)
    SENTENCE_BOUNDARY = re.compile(r'[.!?]\s+')

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        respect_sentence_boundaries: bool = True
    ):
        """
        Initialize text chunker with configuration.

        Args:
            chunk_size: Target size of each chunk in characters
            overlap: Number of overlapping characters between chunks
            respect_sentence_boundaries: Whether to split at sentence boundaries

        Raises:
            ValueError: If chunk_size <= overlap or invalid configuration
        """
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")

        if overlap < 0:
            raise ValueError(f"overlap must be non-negative, got {overlap}")

        if overlap >= chunk_size:
            raise ValueError(
                f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
            )

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.respect_sentence_boundaries = respect_sentence_boundaries

        logger.info(
            f"TextChunker initialized: chunk_size={chunk_size}, "
            f"overlap={overlap}, respect_boundaries={respect_sentence_boundaries}"
        )

    def chunk_text(self, text: str) -> List[TextChunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of TextChunk objects

        Raises:
            ValueError: If text is empty or None
        """
        if not text or not text.strip():
            raise ValueError("Cannot chunk empty or whitespace-only text")

        # Normalize whitespace
        text = self._normalize_text(text)

        # If text is shorter than chunk size, return single chunk
        if len(text) <= self.chunk_size:
            logger.info(f"Text length ({len(text)}) <= chunk_size, returning single chunk")
            return [
                TextChunk(
                    text=text,
                    chunk_index=0,
                    start_char=0,
                    end_char=len(text),
                    content_length=len(text)
                )
            ]

        chunks = []
        chunk_index = 0
        start_pos = 0

        while start_pos < len(text):
            # Determine chunk end position
            end_pos = min(start_pos + self.chunk_size, len(text))

            # If respecting sentence boundaries and not at text end, adjust end position
            if self.respect_sentence_boundaries and end_pos < len(text):
                end_pos = self._find_sentence_boundary(text, start_pos, end_pos)

            # Extract chunk text
            chunk_text = text[start_pos:end_pos].strip()

            # Only add non-empty chunks
            if chunk_text:
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        chunk_index=chunk_index,
                        start_char=start_pos,
                        end_char=end_pos,
                        content_length=len(chunk_text)
                    )
                )
                chunk_index += 1

            # Move to next chunk position with overlap
            # If this was the last chunk, break
            if end_pos >= len(text):
                break

            start_pos = end_pos - self.overlap

            # Prevent infinite loop if overlap causes no progress
            if start_pos <= chunks[-1].start_char:
                start_pos = end_pos

        logger.info(
            f"Chunked text into {len(chunks)} chunks "
            f"(original length: {len(text)} chars)"
        )

        return chunks

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text whitespace.

        Args:
            text: Input text

        Returns:
            Normalized text with consistent whitespace
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)

        # Replace multiple newlines with double newline
        text = re.sub(r'\n\n+', '\n\n', text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _find_sentence_boundary(
        self,
        text: str,
        start_pos: int,
        target_pos: int
    ) -> int:
        """
        Find the nearest sentence boundary before target position.

        Searches backward from target_pos to find a sentence boundary.
        If no boundary is found within reasonable distance, returns target_pos.

        Args:
            text: Full text
            start_pos: Start position of current chunk
            target_pos: Target end position

        Returns:
            Adjusted end position at sentence boundary
        """
        # Search window: look back up to 20% of chunk size
        search_window = min(int(self.chunk_size * 0.2), target_pos - start_pos)
        search_start = max(start_pos, target_pos - search_window)

        # Extract search region
        search_text = text[search_start:target_pos]

        # Find all sentence boundaries in search region
        boundaries = [
            match.end() for match in self.SENTENCE_BOUNDARY.finditer(search_text)
        ]

        if boundaries:
            # Use the last (rightmost) boundary
            boundary_offset = boundaries[-1]
            adjusted_pos = search_start + boundary_offset

            logger.debug(
                f"Found sentence boundary at {adjusted_pos} "
                f"(target was {target_pos})"
            )

            return adjusted_pos
        else:
            # No boundary found, use target position
            logger.debug(
                f"No sentence boundary found near {target_pos}, "
                f"using target position"
            )
            return target_pos

    def get_chunk_metadata(self, chunks: List[TextChunk]) -> dict:
        """
        Get metadata summary for a list of chunks.

        Args:
            chunks: List of TextChunk objects

        Returns:
            Dictionary containing chunk statistics
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "total_characters": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0
            }

        chunk_sizes = [chunk.content_length for chunk in chunks]
        total_chars = sum(chunk_sizes)

        return {
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "avg_chunk_size": total_chars // len(chunks),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes)
        }


def chunk_document_text(
    text: str,
    chunk_size: int = TextChunker.DEFAULT_CHUNK_SIZE,
    overlap: int = TextChunker.DEFAULT_OVERLAP
) -> List[TextChunk]:
    """
    Convenience function to chunk document text.

    Args:
        text: Document text to chunk
        chunk_size: Target chunk size in characters
        overlap: Overlap size in characters

    Returns:
        List of TextChunk objects
    """
    chunker = TextChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk_text(text)
