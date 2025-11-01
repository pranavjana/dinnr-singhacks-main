"""
Configuration management for Payment History Analysis Tool.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # Groq LLM API Configuration
    groq_api_key: str  # Will be loaded from .env
    groq_model: str = "moonshotai/kimi-k2-instruct-0905"

    # Data Source Configuration
    csv_file_path: str = "../transactions_mock_1000_for_participants.csv"

    # Logging Configuration
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

# Global settings instance
settings = Settings()