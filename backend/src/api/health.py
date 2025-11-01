"""
Health check endpoint with system status checks
"""
import logging
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from src.db.connection import test_connection as test_db_connection
from config_modules.celery_config import test_redis_connection
from config_modules.gemini_config import validate_api_key
from src.metrics import get_metrics, get_metrics_content_type
from src.models.schemas import HealthCheckResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def check_database() -> str:
    """
    Check database connectivity

    Returns:
        Status string: "connected" or "disconnected"
    """
    try:
        if test_db_connection():
            return "connected"
        return "disconnected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return "disconnected"


def check_redis() -> str:
    """
    Check Redis connectivity

    Returns:
        Status string: "connected" or "disconnected"
    """
    try:
        if test_redis_connection():
            return "connected"
        return "disconnected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return "disconnected"


def check_gemini_api() -> str:
    """
    Check Gemini API accessibility

    Returns:
        Status string: "accessible" or "inaccessible"
    """
    try:
        if validate_api_key():
            return "accessible"
        return "inaccessible"
    except Exception as e:
        logger.error(f"Gemini API health check failed: {e}")
        return "inaccessible"


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health Check",
    description="Check system health and component status",
    tags=["System"]
)
async def health_check() -> HealthCheckResponse:
    """
    Comprehensive health check endpoint

    Checks:
    - Database connectivity
    - Redis connectivity
    - Gemini API accessibility

    Returns:
        Health status of all components
    """
    # Run all checks
    db_status = check_database()
    redis_status = check_redis()
    gemini_status = check_gemini_api()

    # Determine overall status
    all_healthy = all([
        db_status == "connected",
        redis_status == "connected",
        gemini_status == "accessible"
    ])

    overall_status = "healthy" if all_healthy else "degraded"

    logger.info(
        f"Health check: {overall_status}",
        extra={
            "database": db_status,
            "redis": redis_status,
            "gemini_api": gemini_status
        }
    )

    return HealthCheckResponse(
        status=overall_status,
        database=db_status,
        redis=redis_status,
        gemini_api=gemini_status,
        timestamp=datetime.utcnow()
    )


@router.get(
    "/health/ready",
    summary="Readiness Check",
    description="Check if service is ready to accept requests",
    tags=["System"]
)
async def readiness_check() -> Dict[str, str]:
    """
    Kubernetes readiness probe endpoint

    Returns 200 if service is ready to accept traffic

    Returns:
        Readiness status
    """
    db_status = check_database()

    if db_status == "connected":
        return {"status": "ready"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "database_unavailable"}
        )


@router.get(
    "/health/live",
    summary="Liveness Check",
    description="Check if service is alive",
    tags=["System"]
)
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint

    Returns 200 if service is alive

    Returns:
        Liveness status
    """
    return {"status": "alive"}


@router.get(
    "/metrics",
    summary="Prometheus Metrics",
    description="Expose Prometheus metrics",
    tags=["System"]
)
async def metrics() -> Response:
    """
    Prometheus metrics endpoint

    Returns metrics in Prometheus exposition format

    Returns:
        Metrics in text/plain format
    """
    metrics_data = get_metrics()

    return Response(
        content=metrics_data,
        media_type=get_metrics_content_type()
    )
