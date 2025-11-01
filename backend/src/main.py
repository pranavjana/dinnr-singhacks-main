"""
FastAPI application entry point for PDF Document Processing Pipeline.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Backend service for PDF document ingestion, semantic embedding, and search"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "environment": settings.FASTAPI_ENV,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    Full health check with database/Redis/Gemini status will be in /api/health.py
    """
    return {
        "status": "healthy",
        "service": "pdf-processing-api",
        "version": settings.API_VERSION
    }


# Router registration
# Rule extraction endpoints
from api.rule_extraction import router as extraction_router
app.include_router(extraction_router)

# Future routers will be added here:
# from api import documents, search, health
# app.include_router(documents.router, prefix="/v1/documents", tags=["Documents"])
# app.include_router(search.router, prefix="/v1/search", tags=["Search"])
# app.include_router(health.router, prefix="/v1/health", tags=["Health"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.FASTAPI_ENV == "development"
    )
