"""
FastAPI endpoints for transaction monitoring.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Literal
import structlog
from services.supabase_service import get_supabase_service

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])


class TransactionRequest(BaseModel):
    """Request to save a transaction."""
    payment_id: str | None = None
    trace_id: str | None = None
    amount: float
    currency: str
    originator_name: str | None = None
    beneficiary_name: str | None = None
    merchant: str | None = None
    category: str | None = None
    product_type: str | None = None
    booking_datetime: str | None = None
    transaction_data: dict[str, Any]
    verdict: dict[str, Any] | None = None
    triage: dict[str, Any] | None = None
    is_analyzing: bool = False
    is_triaging: bool = False


class TransactionUpdateRequest(BaseModel):
    """Request to update a transaction."""
    verdict: dict[str, Any] | None = None
    triage: dict[str, Any] | None = None
    is_analyzing: bool | None = None
    is_triaging: bool | None = None
    user_action: str | None = None
    user_action_timestamp: str | None = None
    user_action_by: str | None = None


@router.post("/")
async def create_transaction(request: TransactionRequest):
    """
    Save a new transaction to the database.
    """
    db = get_supabase_service()

    try:
        import asyncio

        transaction_data = {
            "payment_id": request.payment_id,
            "trace_id": request.trace_id,
            "amount": request.amount,
            "currency": request.currency,
            "originator_name": request.originator_name,
            "beneficiary_name": request.beneficiary_name,
            "merchant": request.merchant,
            "category": request.category,
            "product_type": request.product_type,
            "booking_datetime": request.booking_datetime,
            "transaction_data": request.transaction_data,
            "verdict": request.verdict,
            "triage": request.triage,
            "is_analyzing": request.is_analyzing,
            "is_triaging": request.is_triaging,
        }

        result = await asyncio.to_thread(
            lambda: db.client.table("transactions")
            .insert(transaction_data)
            .execute()
        )

        logger.info("Transaction saved", transaction_id=result.data[0]["id"])

        return {"status": "success", "transaction": result.data[0]}

    except Exception as e:
        logger.error("Failed to save transaction", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save transaction: {str(e)}")


@router.get("/")
async def get_transactions(limit: int = 50, has_action: bool | None = None):
    """
    Get recent transactions from the database.

    Args:
        limit: Maximum number of transactions to return
        has_action: If True, only return transactions with user_action set
    """
    db = get_supabase_service()

    try:
        import asyncio

        def fetch_transactions():
            query = db.client.table("transactions").select("*")

            if has_action is True:
                query = query.not_.is_("user_action", "null")
            elif has_action is False:
                query = query.is_("user_action", "null")

            return query.order("created_at", desc=True).limit(limit).execute()

        result = await asyncio.to_thread(fetch_transactions)

        logger.info("Transactions retrieved", count=len(result.data), has_action=has_action)

        return result.data

    except Exception as e:
        logger.error("Failed to retrieve transactions", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to retrieve transactions: {str(e)}")


@router.patch("/{transaction_id}")
async def update_transaction(transaction_id: str, request: TransactionUpdateRequest):
    """
    Update a transaction with verdict and triage information.
    """
    db = get_supabase_service()

    try:
        import asyncio

        update_data = {}
        if request.verdict is not None:
            update_data["verdict"] = request.verdict
        if request.triage is not None:
            update_data["triage"] = request.triage
        if request.is_analyzing is not None:
            update_data["is_analyzing"] = request.is_analyzing
        if request.is_triaging is not None:
            update_data["is_triaging"] = request.is_triaging
        if request.user_action is not None:
            update_data["user_action"] = request.user_action
        if request.user_action_timestamp is not None:
            update_data["user_action_timestamp"] = request.user_action_timestamp
        if request.user_action_by is not None:
            update_data["user_action_by"] = request.user_action_by

        result = await asyncio.to_thread(
            lambda: db.client.table("transactions")
            .update(update_data)
            .eq("id", transaction_id)
            .execute()
        )

        logger.info("Transaction updated", transaction_id=transaction_id)

        return {"status": "success", "transaction": result.data[0]}

    except Exception as e:
        logger.error("Failed to update transaction", transaction_id=transaction_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update transaction: {str(e)}")


@router.delete("/{transaction_id}")
async def delete_transaction(transaction_id: str):
    """
    Delete a transaction.
    """
    db = get_supabase_service()

    try:
        import asyncio

        await asyncio.to_thread(
            lambda: db.client.table("transactions")
            .delete()
            .eq("id", transaction_id)
            .execute()
        )

        logger.info("Transaction deleted", transaction_id=transaction_id)

        return {"status": "success", "message": "Transaction deleted"}

    except Exception as e:
        logger.error("Failed to delete transaction", transaction_id=transaction_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete transaction: {str(e)}")
