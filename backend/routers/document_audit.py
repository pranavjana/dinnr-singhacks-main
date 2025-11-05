"""
Document audit trail router for document analysis logging and querying.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from uuid import uuid4

try:
    from backend.core.observability import get_logger
    from backend.src.db.supabase_client import get_supabase_client
except ModuleNotFoundError:
    from core.observability import get_logger
    from src.db.supabase_client import get_supabase_client

logger = get_logger(__name__)

router = APIRouter()


class DocumentAuditCreate(BaseModel):
    """Request model for creating a document audit entry."""
    document_name: str
    document_type: str
    file_size_kb: float
    uploaded_by: str = "Helen Derinlacs"
    overall_risk_score: float
    risk_level: str
    format_risk: float
    authenticity_risk: float
    word_count: Optional[int] = None
    spell_error_rate: Optional[float] = None
    section_coverage: Optional[float] = None
    status: str = "Complete"
    doc_subtype: Optional[str] = None
    risk_justifications: Optional[List[Dict[str, Any]]] = None
    format_analysis: Optional[Dict[str, Any]] = None
    authenticity_check: Optional[Dict[str, Any]] = None


@router.get("/api/v1/documents/audit")
async def get_document_audit_trail() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get document audit trail entries.

    Returns:
        Dict containing list of document audit entries
    """
    logger.info("get_document_audit_trail - fetching all entries")

    try:
        client = get_supabase_client()

        # Query document_audit_trail table
        response = client.table('document_audit_trail') \
            .select('*') \
            .order('upload_date', desc=True) \
            .limit(100) \
            .execute()

        entries = response.data if response.data else []

        logger.info(f"get_document_audit_trail - found {len(entries)} entries")

        return {"data": entries}

    except Exception as e:
        logger.error(f"get_document_audit_trail - error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch document audit trail: {str(e)}"
        )


@router.post("/api/v1/documents/audit")
async def create_document_audit_entry(
    entry: DocumentAuditCreate
) -> Dict[str, Any]:
    """
    Create a new document audit trail entry.

    Args:
        entry: Document audit entry data

    Returns:
        Created entry with ID and timestamp
    """
    logger.info(
        f"create_document_audit_entry - document={entry.document_name}, "
        f"type={entry.document_type}, risk_level={entry.risk_level}"
    )

    try:
        client = get_supabase_client()

        # Prepare data for insertion
        audit_data = {
            "document_name": entry.document_name,
            "document_type": entry.document_type,
            "file_size_kb": entry.file_size_kb,
            "uploaded_by": entry.uploaded_by,
            "overall_risk_score": entry.overall_risk_score,
            "risk_level": entry.risk_level,
            "format_risk": entry.format_risk,
            "authenticity_risk": entry.authenticity_risk,
            "word_count": entry.word_count,
            "spell_error_rate": entry.spell_error_rate,
            "section_coverage": entry.section_coverage,
            "status": entry.status,
            "doc_subtype": entry.doc_subtype,
            "risk_justifications": entry.risk_justifications,
            "format_analysis": entry.format_analysis,
            "authenticity_check": entry.authenticity_check,
            "upload_date": datetime.utcnow().isoformat()
        }

        # Insert into document_audit_trail table
        response = client.table('document_audit_trail') \
            .insert(audit_data) \
            .execute()

        if not response.data:
            raise Exception("No data returned from insert operation")

        created_entry = response.data[0]

        logger.info(
            f"document_audit_entry_created - id={created_entry.get('id')}, "
            f"document={entry.document_name}"
        )

        return {"data": created_entry}

    except Exception as e:
        logger.error(f"create_document_audit_entry - error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create document audit entry: {str(e)}"
        )
