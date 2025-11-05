"""
Document Analysis Router - endpoints for document upload and format validation.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

try:
    from backend.services.document_service import document_service
    from backend.services.authenticity_service import authenticity_service
    from backend.services.risk_scoring_service import risk_scoring_service
    from backend.models.document import (
        FormatAnalysisResult,
        ComprehensiveAnalysisResult,
        AuthenticityCheck
    )
except ModuleNotFoundError:
    from services.document_service import document_service
    from services.authenticity_service import authenticity_service
    from services.risk_scoring_service import risk_scoring_service
    from models.document import (
        FormatAnalysisResult,
        ComprehensiveAnalysisResult,
        AuthenticityCheck
    )


router = APIRouter()

# Supported file types
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload", response_model=ComprehensiveAnalysisResult, status_code=status.HTTP_200_OK)
async def upload_and_analyze_document(
    file: UploadFile = File(..., description="Document file (PDF, DOCX, PNG, JPG)"),
    doc_type: str = Form(..., description="Document type to validate against (e.g., 'contract', 'report')"),
    subtype: str = Form(None, description="Optional subtype (e.g., 'msa', 'aml_investigation_report')")
) -> ComprehensiveAnalysisResult:
    """
    Upload a document and analyze its format.

    Extracts text from the document and validates:
    - Spelling errors
    - Double spaces
    - Tab usage as indentation
    - Required sections/headers

    Args:
        file: The document file to analyze
        doc_type: Type of document for template validation
        subtype: Optional subtype within the document type

    Returns:
        FormatAnalysisResult with all validation metrics

    Raises:
        HTTPException: If file type is unsupported or processing fails
    """
    # Validate file extension
    file_ext = None
    if file.filename:
        file_ext = "." + file.filename.rsplit(".", 1)[-1].lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    # Extract text from document
    try:
        text = document_service.extract_text(content, file_ext or ".pdf")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text extraction failed: {str(e)}"
        )

    # Validate that we extracted some text
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from the document"
        )

    # Analyze format
    try:
        format_result = document_service.analyze_format(text, doc_type, subtype, include_text=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Format analysis failed: {str(e)}"
        )

    # Perform authenticity checks for image-based documents
    authenticity_check = None
    if file_ext in [".png", ".jpg", ".jpeg", ".pdf"]:
        try:
            images = document_service.get_images_from_content(content, file_ext)
            if images:
                # Check first image (or primary page)
                authenticity_check = authenticity_service.check_authenticity(images[0])
        except Exception as e:
            # Authenticity check is optional, don't fail the whole request
            pass

    # If no images, mark as not applicable
    if not authenticity_check:
        authenticity_check = AuthenticityCheck(applicable=False)

    # Calculate risk scores
    try:
        template = document_service.load_template(doc_type, subtype)
        format_risk, format_justifications = risk_scoring_service.calculate_format_risk(
            format_result, template
        )
        auth_risk, auth_justifications = risk_scoring_service.calculate_authenticity_risk(
            authenticity_check
        )
        risk_assessment = risk_scoring_service.aggregate_risk_score(
            format_risk, format_justifications,
            auth_risk, auth_justifications
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk scoring failed: {str(e)}"
        )

    # Return comprehensive result
    return ComprehensiveAnalysisResult(
        format_analysis=format_result,
        authenticity_check=authenticity_check,
        risk_assessment=risk_assessment
    )


@router.get("/templates")
async def list_templates() -> dict:
    """
    List available document type templates.

    Returns:
        Dictionary with available template types
    """
    templates = document_service.list_available_templates()
    return {
        "templates": templates,
        "count": len(templates)
    }


@router.get("/templates/{doc_type}")
async def get_template(doc_type: str) -> dict:
    """
    Get template configuration for a specific document type.

    Args:
        doc_type: Document type name

    Returns:
        Template configuration with available subtypes
    """
    try:
        template = document_service.load_template(doc_type)
        subtypes = document_service.list_subtypes(doc_type)
        return {
            "doc_type": doc_type,
            "template": template,
            "subtypes": subtypes
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {str(e)}"
        )
