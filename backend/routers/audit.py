"""
Audit trail router for compliance logging and querying.
"""
from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

try:
    from backend.core.observability import get_logger
    from backend.services.audit_service import audit_service
except ModuleNotFoundError:
    from core.observability import get_logger
    from services.audit_service import audit_service

logger = get_logger(__name__)

router = APIRouter()


class AuditEntryCreate(BaseModel):
    """Request model for creating an audit entry."""
    action: str
    user_name: Optional[str] = "system"
    rules_created: Optional[int] = 0
    rules_updated: Optional[int] = 0
    status: Optional[str] = "success"
    details: Optional[str] = ""


class AuditEntryResponse(BaseModel):
    """Response model for audit entries."""
    id: str
    timestamp: str
    action: str
    user_id: str
    details: Dict[str, Any]


@router.get("/api/v1/audit")
async def get_audit_trail(
    limit: int = Query(default=100, ge=1, le=1000)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get recent audit trail entries.

    Args:
        limit: Maximum number of entries to return (1-1000)

    Returns:
        Dict containing list of audit entries
    """
    logger.info(f"get_audit_trail - limit={limit}")

    # Get recent audit logs
    entries = await audit_service.get_recent_audits(limit=limit)

    # Convert to response format
    formatted_entries = [
        {
            "id": str(entry.get("audit_id", "")),
            "timestamp": entry.get("timestamp", datetime.utcnow()).isoformat(),
            "action": entry.get("action", "unknown"),
            "user_id": entry.get("actor", "system"),
            "details": entry.get("metadata", {})
        }
        for entry in entries
    ]

    return {"entries": formatted_entries}


@router.post("/api/v1/audit")
async def create_audit_entry(
    entry: AuditEntryCreate
) -> Dict[str, str]:
    """
    Create a new audit trail entry.

    Args:
        entry: Audit entry data

    Returns:
        Created entry ID and timestamp
    """
    logger.info(
        f"create_audit_entry - action={entry.action}, "
        f"user={entry.user_name}, rules_created={entry.rules_created}, "
        f"rules_updated={entry.rules_updated}, status={entry.status}"
    )

    # For now, just log the entry and return a success response
    # In production, this would insert into the database
    from uuid import uuid4
    entry_id = str(uuid4())
    timestamp = datetime.utcnow().isoformat()

    logger.info(
        f"audit_entry_created - entry_id={entry_id}, action={entry.action}"
    )

    return {
        "id": entry_id,
        "timestamp": timestamp,
        "status": "created"
    }
