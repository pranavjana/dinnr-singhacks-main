"""
Document analysis models.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box coordinates for text region."""
    left: float = Field(..., description="Left X coordinate")
    top: float = Field(..., description="Top Y coordinate")
    right: float = Field(..., description="Right X coordinate")
    bottom: float = Field(..., description="Bottom Y coordinate")
    page: int = Field(..., description="Page number (1-indexed)")


class TextRegion(BaseModel):
    """Text region with coordinates."""
    text: str = Field(..., description="Text content")
    bbox: List[float] = Field(..., description="Bounding box [left, top, right, bottom]")
    page: int = Field(..., description="Page number")
    confidence: Optional[float] = Field(None, description="OCR confidence (0-1)")


class IssueCoordinates(BaseModel):
    """Coordinates for a specific issue."""
    issue_type: str = Field(..., description="Type of issue (double_spaces, spelling_error, etc)")
    regions: List[TextRegion] = Field(default_factory=list, description="Regions where issue occurs")


class FormatAnalysisResult(BaseModel):
    """Result of document format analysis."""

    word_count: int = Field(..., description="Total word count in document")
    spell_error_rate: float = Field(..., description="Spelling error rate (0.0 to 1.0)", ge=0, le=1)
    double_space_count: int = Field(..., description="Number of double space occurrences", ge=0)
    tab_count: int = Field(..., description="Number of tab characters used as indent", ge=0)
    headers_found: list[str] = Field(default_factory=list, description="Headers/sections found in document")
    missing_sections: list[str] = Field(default_factory=list, description="Required sections missing from document")
    section_coverage: float = Field(default=1.0, description="Percentage of required sections present", ge=0, le=1)
    extracted_text: Optional[str] = Field(None, description="Full extracted text for highlighting")
    issue_coordinates: List[IssueCoordinates] = Field(default_factory=list, description="Coordinates of detected issues")
    words: List[TextRegion] = Field(default_factory=list, description="All words with coordinates")
    pages: int = Field(1, description="Total number of pages")


class ExifData(BaseModel):
    """EXIF metadata from image."""

    present: bool = Field(..., description="Whether EXIF data is present")
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software: Optional[str] = None
    datetime: Optional[str] = None
    gps_coords: Optional[dict] = None
    anomalies: list[str] = Field(default_factory=list, description="EXIF anomalies detected")


class PHashResult(BaseModel):
    """Perceptual hash result."""

    hash_value: str = Field(..., description="Hex string of perceptual hash")
    duplicates_found: list[dict] = Field(default_factory=list, description="List of duplicate matches")
    similarity_scores: list[float] = Field(default_factory=list, description="Similarity scores (0-1)")


class ELAResult(BaseModel):
    """Error Level Analysis result."""

    mean_score: float = Field(..., description="Mean ELA score", ge=0)
    variance: float = Field(..., description="Variance in ELA", ge=0)
    anomaly_detected: bool = Field(..., description="Whether tampering anomaly detected")
    confidence: float = Field(..., description="Confidence score", ge=0, le=1)


class ReverseImageMatch(BaseModel):
    """Single reverse image search match."""

    url: str = Field(..., description="URL where image was found")
    page_title: Optional[str] = None
    source: str = Field(..., description="Source of the match (e.g., 'Google Vision - Full Match')")
    similarity: Optional[float] = Field(None, description="Similarity score (0-1)", ge=0, le=1)
    source_type: Optional[str] = Field(None, description="e.g., 'stock', 'marketplace', 'social'")


class ReverseImageSearchResult(BaseModel):
    """Reverse image search results."""

    exact_matches: list[ReverseImageMatch] = Field(default_factory=list)
    partial_matches: list[ReverseImageMatch] = Field(default_factory=list)
    total_matches: int = Field(0, ge=0)
    authenticity_risk: str = Field("Low", description="Low/Med/High based on matches")


class AIGenerationHeuristic(BaseModel):
    """AI generation detection heuristic."""

    likelihood: float = Field(..., description="Likelihood of AI generation (0-1)", ge=0, le=1)
    indicators: list[str] = Field(default_factory=list, description="Indicators found")
    confidence: str = Field(..., description="Low/Med/High confidence")


class AuthenticityCheck(BaseModel):
    """Complete authenticity check result."""

    exif: Optional[ExifData] = None
    phash: Optional[PHashResult] = None
    ela: Optional[ELAResult] = None
    reverse_search: Optional[ReverseImageSearchResult] = None
    ai_generation: Optional[AIGenerationHeuristic] = None
    applicable: bool = Field(..., description="Whether authenticity checks apply (images only)")


class RiskJustification(BaseModel):
    """Individual risk justification."""

    category: str = Field(..., description="e.g., 'format', 'authenticity', 'duplication'")
    severity: int = Field(..., description="Severity score", ge=0, le=10)
    reason: str = Field(..., description="Human-readable reason")
    evidence: Optional[dict] = None


class RiskAssessment(BaseModel):
    """Overall risk assessment."""

    overall_score: float = Field(..., description="Overall risk score (0-100)", ge=0, le=100)
    risk_level: str = Field(..., description="Low/Med/High")
    format_risk: float = Field(0, description="Format risk component (0-100)", ge=0, le=100)
    authenticity_risk: float = Field(0, description="Authenticity risk component (0-100)", ge=0, le=100)
    justifications: list[RiskJustification] = Field(default_factory=list)


class ComprehensiveAnalysisResult(BaseModel):
    """Complete document analysis result."""

    format_analysis: FormatAnalysisResult
    authenticity_check: Optional[AuthenticityCheck] = None
    risk_assessment: RiskAssessment
