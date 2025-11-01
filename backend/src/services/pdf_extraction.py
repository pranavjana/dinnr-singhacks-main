"""
PDF text extraction service using pdfplumber with pypdf fallback.

This module provides robust PDF text extraction with:
- Primary extraction using pdfplumber (better table/structure handling)
- Fallback to pypdf for corrupted or encrypted PDFs
- PDF signature validation to prevent malformed file processing
- Extraction confidence scoring based on content completeness
"""

import hashlib
import logging
from typing import Tuple, Optional

import pdfplumber
import pypdf

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Custom exception for PDF extraction failures"""
    pass


class InvalidPDFError(PDFExtractionError):
    """Raised when PDF signature validation fails"""
    pass


def validate_pdf_signature(file_bytes: bytes) -> bool:
    """
    Validate PDF file signature using magic bytes check.

    Args:
        file_bytes: Raw PDF file content

    Returns:
        True if valid PDF signature detected

    Raises:
        InvalidPDFError: If file doesn't have valid PDF signature
    """
    # Check PDF header magic bytes
    if not file_bytes.startswith(b"%PDF"):
        raise InvalidPDFError("Invalid PDF header - missing %PDF magic bytes")

    # Basic size validation
    if len(file_bytes) < 100:
        raise InvalidPDFError("File too small to be a valid PDF")

    return True


def calculate_file_hash(content: str) -> str:
    """
    Calculate SHA-256 hash of extracted text content for deduplication.

    Args:
        content: Extracted text content

    Returns:
        SHA-256 hash as hex string
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def calculate_extraction_confidence(
    file_bytes: bytes,
    extracted_text: str,
    page_count: int
) -> float:
    """
    Calculate extraction confidence score based on content completeness.

    Heuristic:
    - Compare extracted character count vs expected (file_size / page_count)
    - PDFs with images or scanned content will have lower scores
    - Text-heavy documents should score >0.9

    Args:
        file_bytes: Original PDF file bytes
        extracted_text: Extracted text content
        page_count: Number of pages in PDF

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if page_count == 0:
        return 0.0

    # Rough heuristic: expect ~500 chars per page for text documents
    expected_chars = page_count * 500
    actual_chars = len(extracted_text.strip())

    if actual_chars == 0:
        return 0.0

    # Calculate ratio, capped at 1.0 (some PDFs have lots of text)
    confidence = min(actual_chars / expected_chars, 1.0)

    # Boost confidence if we extracted reasonable content
    if actual_chars > page_count * 100:  # At least 100 chars per page
        confidence = max(confidence, 0.7)

    return round(confidence, 2)


def extract_text_with_pdfplumber(file_bytes: bytes) -> Tuple[str, int, float, str]:
    """
    Extract text from PDF using pdfplumber (primary method).

    pdfplumber provides better:
    - Table extraction and preservation
    - Layout structure retention
    - Multi-column document handling

    Args:
        file_bytes: Raw PDF file content

    Returns:
        Tuple of (extracted_text, page_count, confidence_score, method)

    Raises:
        PDFExtractionError: If extraction fails
    """
    try:
        # Validate PDF signature first
        validate_pdf_signature(file_bytes)

        # Use pdfplumber for extraction
        import io
        pdf_file = io.BytesIO(file_bytes)

        extracted_pages = []
        page_count = 0

        with pdfplumber.open(pdf_file) as pdf:
            page_count = len(pdf.pages)

            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_pages.append(text)

        # Combine all pages
        full_text = "\n\n--- Page Break ---\n\n".join(extracted_pages)

        # Calculate confidence
        confidence = calculate_extraction_confidence(file_bytes, full_text, page_count)

        logger.info(
            f"PDF extraction successful with pdfplumber: "
            f"{page_count} pages, {len(full_text)} chars, confidence={confidence}"
        )

        return full_text, page_count, confidence, "pdfplumber"

    except InvalidPDFError:
        raise
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {str(e)}, will try fallback")
        raise PDFExtractionError(f"pdfplumber extraction failed: {str(e)}")


def extract_text_with_pypdf_fallback(file_bytes: bytes) -> Tuple[str, int, float, str]:
    """
    Extract text from PDF using pypdf (fallback method).

    pypdf is used as fallback when pdfplumber fails (e.g., encrypted PDFs).
    Generally lower quality extraction than pdfplumber.

    Args:
        file_bytes: Raw PDF file content

    Returns:
        Tuple of (extracted_text, page_count, confidence_score, method)

    Raises:
        PDFExtractionError: If extraction fails
    """
    try:
        import io
        pdf_file = io.BytesIO(file_bytes)

        reader = pypdf.PdfReader(pdf_file)
        page_count = len(reader.pages)

        extracted_pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_pages.append(text)

        full_text = "\n\n--- Page Break ---\n\n".join(extracted_pages)

        # Lower confidence for fallback method
        confidence = calculate_extraction_confidence(file_bytes, full_text, page_count)
        confidence = max(confidence - 0.1, 0.0)  # Penalize fallback method

        logger.info(
            f"PDF extraction successful with pypdf fallback: "
            f"{page_count} pages, {len(full_text)} chars, confidence={confidence}"
        )

        return full_text, page_count, confidence, "pypdf_fallback"

    except Exception as e:
        logger.error(f"pypdf fallback extraction also failed: {str(e)}")
        raise PDFExtractionError(f"All extraction methods failed: {str(e)}")


def extract_pdf_content(file_bytes: bytes) -> Tuple[str, int, float, str, str]:
    """
    Main entry point for PDF text extraction with automatic fallback.

    Tries pdfplumber first, falls back to pypdf if pdfplumber fails.

    Args:
        file_bytes: Raw PDF file content

    Returns:
        Tuple of (extracted_text, page_count, confidence_score, extraction_method, file_hash)

    Raises:
        InvalidPDFError: If PDF signature validation fails
        PDFExtractionError: If all extraction methods fail
    """
    # Validate PDF signature before any extraction attempt
    validate_pdf_signature(file_bytes)

    # Try pdfplumber first
    try:
        text, page_count, confidence, method = extract_text_with_pdfplumber(file_bytes)
    except PDFExtractionError:
        # Fall back to pypdf
        logger.info("Attempting pypdf fallback extraction")
        text, page_count, confidence, method = extract_text_with_pypdf_fallback(file_bytes)

    # Calculate file hash for deduplication
    file_hash = calculate_file_hash(text)

    logger.info(
        f"PDF extraction complete: method={method}, "
        f"pages={page_count}, confidence={confidence}, hash={file_hash[:16]}..."
    )

    return text, page_count, confidence, method, file_hash


def get_pdf_metadata(file_bytes: bytes) -> dict:
    """
    Extract PDF metadata without full text extraction.

    Useful for quick validation before committing to full extraction.

    Args:
        file_bytes: Raw PDF file content

    Returns:
        Dictionary with metadata: page_count, file_size, has_text
    """
    try:
        import io
        pdf_file = io.BytesIO(file_bytes)

        with pdfplumber.open(pdf_file) as pdf:
            page_count = len(pdf.pages)

            # Check if first page has extractable text
            has_text = False
            if page_count > 0:
                first_page_text = pdf.pages[0].extract_text()
                has_text = bool(first_page_text and len(first_page_text.strip()) > 50)

        return {
            "page_count": page_count,
            "file_size_bytes": len(file_bytes),
            "has_extractable_text": has_text
        }

    except Exception as e:
        logger.error(f"Failed to extract PDF metadata: {str(e)}")
        raise PDFExtractionError(f"Metadata extraction failed: {str(e)}")
