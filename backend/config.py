"""
Backend configuration for PDF Document Processing Pipeline.
Loads environment variables and provides configuration settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # FastAPI
    FASTAPI_ENV: str = Field(default="development", env="FASTAPI_ENV")
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    API_TITLE: str = "PDF Document Processing API"
    API_VERSION: str = "1.0.0"

    # CORS - stored as string in env, parsed to list
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        env="CORS_ORIGINS",
        exclude=True
    )

    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Parse CORS_ORIGINS from comma-separated string."""
        if isinstance(self.cors_origins_str, list):
            return self.cors_origins_str
        return [origin.strip() for origin in self.cors_origins_str.split(",")]

    # Database
    DATABASE_URL: str = Field(env="DATABASE_URL")
    DB_POOL_SIZE: int = Field(default=10, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=20, env="DB_MAX_OVERFLOW")

    # Supabase
    SUPABASE_URL: str = Field(env="SUPABASE_URL")
    SUPABASE_KEY: str = Field(env="SUPABASE_KEY")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(env="SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_BUCKET_NAME: str = Field(default="compliance-pdfs", env="SUPABASE_BUCKET_NAME")

    @property
    def SUPABASE_SERVICE_KEY(self) -> str:
        """Alias for SUPABASE_SERVICE_ROLE_KEY."""
        return self.SUPABASE_SERVICE_ROLE_KEY

    # Gemini API
    GOOGLE_API_KEY: str = Field(env="GOOGLE_API_KEY")
    GEMINI_MODEL: str = Field(default="models/embedding-001", env="GEMINI_MODEL")
    GEMINI_TIMEOUT_SECONDS: int = Field(default=30, env="GEMINI_TIMEOUT_SECONDS")

    # Groq API (for rule extraction)
    GROQ_API_KEY: str = Field(env="GROQ_API_KEY")
    GROQ_MODEL: str = Field(default="moonshotai/kimi-k2-instruct-0905", env="GROQ_MODEL")

    # Redis & Celery
    REDIS_URL: str = Field(env="REDIS_URL")
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # Processing Configuration
    BATCH_SIZE: int = Field(default=50, env="BATCH_SIZE")  # Documents per hour
    PDF_EXTRACTION_TIMEOUT: int = Field(default=60, env="PDF_EXTRACTION_TIMEOUT")  # seconds
    MAX_EMBEDDING_RETRIES: int = Field(default=3, env="MAX_EMBEDDING_RETRIES")
    RETRY_INITIAL_DELAY: int = Field(default=1800, env="RETRY_INITIAL_DELAY")  # 30 minutes in seconds
    RETRY_BACKOFF_MULTIPLIER: int = Field(default=2, env="RETRY_BACKOFF_MULTIPLIER")
    RETRY_MAX_DELAY: int = Field(default=86400, env="RETRY_MAX_DELAY")  # 24 hours

    # Performance Targets
    VECTOR_SEARCH_TIMEOUT: int = Field(default=500, env="VECTOR_SEARCH_TIMEOUT")  # milliseconds
    HNSW_EF_SEARCH: int = Field(default=100, env="HNSW_EF_SEARCH")  # pgvector parameter

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = "json"  # json or text

    # Annual Refresh Schedule
    ANNUAL_REFRESH_MONTH: int = Field(default=11, env="ANNUAL_REFRESH_MONTH")  # November
    ANNUAL_REFRESH_DAY: int = Field(default=1, env="ANNUAL_REFRESH_DAY")
    ANNUAL_REFRESH_HOUR: int = Field(default=0, env="ANNUAL_REFRESH_HOUR")

    # Processor Version (for audit trail)
    PROCESSOR_VERSION: str = Field(default="1.0.0", env="PROCESSOR_VERSION")

    # Testing
    IS_TESTING: bool = Field(default=False, env="IS_TESTING")
    DEBUG: bool = Field(default=False, env="DEBUG")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set Celery URLs from Redis if not explicitly provided
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance."""
    return settings
