"""
Configuration management using Pydantic settings.
Loads environment variables from .env file and provides type-safe access.
"""
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str
    supabase_url: str
    supabase_key: str
    
    # LLM Configuration
    groq_api_key: str
    llm_model: str = "kimi-k2-0905"
    groq_model: str = "moonshotai/kimi-k2-instruct-0905"  # Alternative model name
    
    # Application Configuration
    environment: str = "development"
    log_level: str = "INFO"
    debug: bool = True

    # Optional: Make some fields optional with defaults
    langsmith_api_key: str = ""
    
    # Performance Configuration
    max_concurrent_requests: int = 100
    database_pool_size: int = 20
    analysis_timeout_seconds: int = 30
    
    # Pattern Detection Thresholds
    structuring_threshold: float = 10000.0
    velocity_sigma_threshold: float = 5.0
    high_risk_jurisdictions: str = "KP,IR,SY,MM"

    # Data Sources
    transactions_csv_path: str = Field(
        default=str(Path(__file__).resolve().parents[2] / "transactions_mock_1000_for_participants.csv"),
        env="TRANSACTIONS_CSV_PATH",
        description="Path to historical transactions CSV used for LLM analysis"
    )

    # Observability Configuration
    enable_metrics: bool = True
    metrics_port: int = 9090
    
    # CORS Configuration
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from other features
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as list."""
        return self.cors_origins
    
    @property
    def high_risk_jurisdictions_list(self) -> List[str]:
        """Convert high-risk jurisdictions string to list."""
        return [code.strip() for code in self.high_risk_jurisdictions.split(",")]


# Global settings instance
settings = Settings()
