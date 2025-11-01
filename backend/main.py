"""
FastAPI application entry point for AML Payment Analysis API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings
from backend.core.observability import (
    get_logger,
    get_metrics,
    get_metrics_content_type
)

# Initialize logger
logger = get_logger(__name__)

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
from backend.routers import payment_analysis

app.include_router(
    payment_analysis.router,
    prefix="/api/v1/payments",
    tags=["Payment Analysis"]
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
