"""
Document processing service for text extraction and format analysis.
"""

import io
import re
from pathlib import Path
from typing import BinaryIO, Optional

import pdfplumber
import pytesseract
import yaml
from docx import Document
from PIL import Image
from spellchecker import SpellChecker

try:
    from backend.models.document import FormatAnalysisResult
except ModuleNotFoundError:
    from models.document import FormatAnalysisResult


class DocumentService:
    """Service for extracting text from documents and analyzing format."""

    def __init__(self, templates_dir: str = "templates/document_schemas"):
        """Initialize document service.

        Args:
            templates_dir: Directory containing YAML template files
        """
        self.templates_dir = Path(templates_dir)
        self.spell_checker = SpellChecker()
        self._template_cache: dict[str, dict] = {}

    def extract_text(self, file_content: bytes, file_type: str) -> str:
        """Extract text from document based on file type.

        Args:
            file_content: Binary content of the file
            file_type: File extension (pdf, docx, png, jpg, jpeg)

        Returns:
            Extracted text content

        Raises:
            ValueError: If file type is not supported
        """
        file_type = file_type.lower().replace(".", "")

        if file_type == "pdf":
            return self._extract_from_pdf(file_content)
        elif file_type == "docx":
            return self._extract_from_docx(file_content)
        elif file_type in ["png", "jpg", "jpeg"]:
            return self._extract_from_image(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _extract_from_pdf(self, content: bytes) -> str:
        """Extract text from PDF using pdfplumber.

        Falls back to OCR if no text is found (scanned PDFs).
        """
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text)
                else:
                    # No text found - try OCR on page image
                    try:
                        img = page.to_image(resolution=300)
                        pil_image = img.original
                        ocr_text = pytesseract.image_to_string(pil_image)
                        if ocr_text and ocr_text.strip():
                            text_parts.append(ocr_text)
                    except Exception as e:
                        # If OCR fails, continue with next page
                        pass
        return "\n\n".join(text_parts)

    def _extract_from_docx(self, content: bytes) -> str:
        """Extract text from DOCX using python-docx."""
        doc = Document(io.BytesIO(content))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(paragraphs)

    def _extract_from_image(self, content: bytes) -> str:
        """Extract text from image using pytesseract OCR."""
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image)
        return text.strip()

    def get_images_from_content(self, file_content: bytes, file_type: str) -> list[Image.Image]:
        """Extract images from document for authenticity checking.

        Args:
            file_content: Binary content of the file
            file_type: File extension

        Returns:
            List of PIL Image objects
        """
        file_type = file_type.lower().replace(".", "")
        images = []

        if file_type in ["png", "jpg", "jpeg"]:
            # Direct image file
            try:
                image = Image.open(io.BytesIO(file_content))
                images.append(image)
            except:
                pass

        elif file_type == "pdf":
            # Extract images from PDF pages
            try:
                with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                    for page in pdf.pages:
                        try:
                            # Convert page to image
                            img = page.to_image(resolution=150)
                            pil_image = img.original
                            images.append(pil_image)
                        except:
                            pass
            except:
                pass

        return images

    def load_template(self, doc_type: str, subtype: Optional[str] = None) -> dict:
        """Load YAML template for document type.

        Args:
            doc_type: Document type (e.g., 'contract', 'report')
            subtype: Optional subtype (e.g., 'msa', 'aml_investigation_report')

        Returns:
            Template configuration dictionary
        """
        cache_key = f"{doc_type}:{subtype}" if subtype else doc_type
        if cache_key in self._template_cache:
            return self._template_cache[cache_key]

        template_path = self.templates_dir / f"{doc_type}.yaml"
        if not template_path.exists():
            # Return default template if specific one doesn't exist
            return {
                "required_headers": [],
                "optional_headers": [],
                "spelling_error_rate_max": 0.05,
                "spacing_rules": {
                    "max_double_space_ratio": 0.05,
                    "max_tabs": 30
                }
            }

        with open(template_path, "r") as f:
            template_data = yaml.safe_load(f)

            # If subtype specified, extract that specific config
            if subtype and subtype in template_data:
                template = template_data[subtype]
            else:
                # Use the whole template for backwards compatibility
                template = template_data

            self._template_cache[cache_key] = template
            return template

    def analyze_format(self, text: str, doc_type: str, subtype: Optional[str] = None, include_text: bool = False) -> FormatAnalysisResult:
        """Analyze document format against template.

        Args:
            text: Extracted text content
            doc_type: Document type to validate against
            subtype: Optional subtype within the document type
            include_text: Whether to include extracted text in result

        Returns:
            FormatAnalysisResult with all metrics
        """
        template = self.load_template(doc_type, subtype)

        # Word count
        words = text.split()
        word_count = len(words)

        # Spelling analysis
        spell_error_rate, _ = self._check_spelling(text)

        # Formatting issues
        double_space_count = self._count_double_spaces(text)
        tab_count = self._count_tabs_as_indent(text)

        # Header/section analysis - support both old and new format
        headers_found = self._find_headers(text)
        required_sections = template.get("required_headers", template.get("required_sections", []))
        missing_sections = self._find_missing_sections(headers_found, required_sections)

        # Section coverage
        if required_sections:
            section_coverage = (len(required_sections) - len(missing_sections)) / len(required_sections)
        else:
            section_coverage = 1.0

        return FormatAnalysisResult(
            word_count=word_count,
            spell_error_rate=spell_error_rate,
            double_space_count=double_space_count,
            tab_count=tab_count,
            headers_found=headers_found,
            missing_sections=missing_sections,
            section_coverage=section_coverage,
            extracted_text=text if include_text else None
        )

    def _check_spelling(self, text: str) -> tuple[float, list[str]]:
        """Check spelling and return error rate.

        Returns:
            Tuple of (error_rate, list of misspelled words)
        """
        # Extract words and filter out non-alphabetic
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        if not words:
            return 0.0, []

        # Check spelling
        misspelled = list(self.spell_checker.unknown(words))
        error_rate = len(misspelled) / len(words) if words else 0.0

        return error_rate, misspelled

    def _count_double_spaces(self, text: str) -> int:
        """Count occurrences of double spaces."""
        return text.count("  ")

    def _count_tabs_as_indent(self, text: str) -> int:
        """Count tab characters used as indentation."""
        # Count tabs at start of lines
        lines = text.split("\n")
        tab_count = sum(1 for line in lines if line.startswith("\t"))
        return tab_count

    def _find_headers(self, text: str) -> list[str]:
        """Find headers/section titles in text.

        Detects:
        - Lines that are all caps
        - Lines ending with colon
        - Short lines (< 50 chars) that are title-cased
        """
        headers = []
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # All caps lines (at least 3 chars)
            if len(line) >= 3 and line.isupper() and not line.isdigit():
                headers.append(line)
                continue

            # Lines ending with colon
            if line.endswith(":") and len(line) < 50:
                headers.append(line.rstrip(":"))
                continue

            # Title case short lines
            words = line.split()
            if len(line) < 50 and len(words) <= 6:
                if all(word[0].isupper() or not word[0].isalpha() for word in words if word):
                    headers.append(line)

        return headers

    def _find_missing_sections(self, headers_found: list[str], required_sections: list[str]) -> list[str]:
        """Find which required sections are missing.

        Uses fuzzy matching (case-insensitive, partial match).
        """
        headers_lower = [h.lower() for h in headers_found]
        missing = []

        for required in required_sections:
            required_lower = required.lower()
            # Check if any found header contains the required section name
            found = any(required_lower in header or header in required_lower
                       for header in headers_lower)
            if not found:
                missing.append(required)

        return missing

    def list_available_templates(self) -> list[str]:
        """List all available document type templates.

        Returns:
            List of document types (without .yaml extension)
        """
        if not self.templates_dir.exists():
            return []

        templates = []
        for file in self.templates_dir.glob("*.yaml"):
            templates.append(file.stem)
        return sorted(templates)

    def list_subtypes(self, doc_type: str) -> list[str]:
        """List all subtypes available for a document type.

        Args:
            doc_type: Document type (e.g., 'contract', 'report')

        Returns:
            List of subtype names (e.g., ['msa', 'sow', 'nda'])
        """
        template_path = self.templates_dir / f"{doc_type}.yaml"
        if not template_path.exists():
            return []

        with open(template_path, "r") as f:
            template_data = yaml.safe_load(f)

        # Find keys that don't start with underscore (those are subtypes)
        subtypes = [key for key in template_data.keys() if not key.startswith("_")]
        return sorted(subtypes)


# Singleton instance
document_service = DocumentService()
