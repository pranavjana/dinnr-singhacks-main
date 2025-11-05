"""
FastAPI application entry point for AML Payment Analysis API.
"""

from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try both import styles (running from backend dir vs parent dir)
try:
    from backend.core.config import settings
    from backend.core.observability import (
        get_logger,
        get_metrics,
        get_metrics_content_type
    )
except ModuleNotFoundError:
    from core.config import settings
    from core.observability import (
        get_logger,
        get_metrics,
        get_metrics_content_type
    )

# Initialize logger
logger = get_logger(__name__)

# Set Google Cloud credentials environment variable if configured
if settings.google_application_credentials:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = settings.google_application_credentials
    logger.info(f"Google Cloud credentials configured: {settings.google_application_credentials}")

# Create FastAPI app
app = FastAPI(
    title="AML Payment Analysis API",
    description="Real-time AML risk assessment with rule checking and pattern detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        f"application_startup - environment={settings.environment}, log_level={settings.log_level}"
    )

    # Debug: Print all registered routes
    logger.info("=" * 50)
    logger.info("Registered routes:")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            logger.info(f"  {route.methods} {route.path}")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("application_shutdown")


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns service status and dependency health.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "dependencies": {
            "database": "unknown",  # Will be updated when DB service is added
            "groq_api": "unknown"  # Will be updated when Groq service is added
        }
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in OpenMetrics format.
    """
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "AML Payment Analysis API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics"
    }


# Register routers
try:
    # Try both import styles (running from backend dir vs parent dir)
    try:
        from backend.routers import payment_analysis
    except ModuleNotFoundError:
        from routers import payment_analysis

    # Payment analysis endpoints
    app.include_router(
        payment_analysis.router,
        prefix="/api/v1/payments",
        tags=["Payment Analysis"]
    )
    logger.info("Payment analysis endpoints registered successfully at /api/v1/payments")
except Exception as e:
    logger.error(f"Failed to load payment analysis endpoints: {e}")
    import traceback
    traceback.print_exc()

# Rule extraction endpoints (from src/api)
try:
    import sys
    import os
    src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from api.rule_extraction import router as extraction_router
    app.include_router(extraction_router, tags=["Rule Extraction"])
    logger.info("Rule extraction endpoints registered successfully")
except Exception as e:
    logger.warning(f"Could not load rule extraction endpoints: {e}")
    logger.info("Continuing without rule extraction endpoints...")


# Transaction monitoring endpoints (from src/api)
try:
    from api.transactions import router as transactions_router
    app.include_router(transactions_router, tags=["Transactions"])
    logger.info("Transaction monitoring endpoints registered successfully")
except Exception as e:
    logger.warning(f"Could not load transaction monitoring endpoints: {e}")
    logger.info("Continuing without transaction monitoring endpoints...")
# Document analysis endpoints
try:
    try:
        from backend.routers import document_analysis
    except ModuleNotFoundError:
        from routers import document_analysis

    app.include_router(
        document_analysis.router,
        prefix="/api/v1/documents",
        tags=["Document Analysis"]
    )
    logger.info("Document analysis endpoints registered successfully at /api/v1/documents")
except Exception as e:
    logger.error(f"Failed to load document analysis endpoints: {e}")
    import traceback
    traceback.print_exc()

# Audit trail endpoints
try:
    try:
        from backend.routers import audit
    except ModuleNotFoundError:
        from routers import audit

    app.include_router(
        audit.router,
        tags=["Audit Trail"]
    )
    logger.info("Audit trail endpoints registered successfully")
except Exception as e:
    logger.error(f"Failed to load audit trail endpoints: {e}")
    import traceback
    traceback.print_exc()

# Document audit trail endpoints
try:
    try:
        from backend.routers import document_audit
    except ModuleNotFoundError:
        from routers import document_audit

    app.include_router(
        document_audit.router,
        tags=["Document Audit Trail"]
    )
    logger.info("Document audit trail endpoints registered successfully")
except Exception as e:
    logger.error(f"Failed to load document audit trail endpoints: {e}")
    import traceback
    traceback.print_exc()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
