"""
Google Gemini API client configuration
Handles API key validation and model configuration for embeddings
"""
import logging
from functools import lru_cache
from typing import Optional

import google.generativeai as genai

from config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def configure_gemini_api() -> None:
    """
    Configure Google Generative AI SDK with API key

    Raises:
        ValueError: If GOOGLE_API_KEY not configured
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY must be configured in environment")

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    logger.info("Gemini API configured successfully")


def validate_api_key() -> bool:
    """
    Validate Gemini API key by making a test request

    Returns:
        True if API key is valid, False otherwise
    """
    try:
        configure_gemini_api()

        # List available models to test API key
        models = genai.list_models()
        model_names = [m.name for m in models]

        logger.info(f"API key validation successful. Available models: {len(model_names)}")
        return True

    except Exception as e:
        logger.error(f"API key validation failed: {e}")
        return False


def get_embedding_model(model_name: Optional[str] = None):
    """
    Get configured embedding model

    Args:
        model_name: Override default model (optional)

    Returns:
        Configured GenerativeModel instance

    Raises:
        ValueError: If model not found
    """
    configure_gemini_api()

    model = model_name or settings.GEMINI_MODEL

    if not model:
        raise ValueError("GEMINI_MODEL must be configured in environment")

    try:
        # Verify model exists and supports embeddings
        available_models = genai.list_models()
        embedding_models = [
            m for m in available_models
            if 'embedContent' in m.supported_generation_methods
        ]

        model_names = [m.name for m in embedding_models]

        # Handle model name with or without 'models/' prefix
        full_model_name = f"models/{model}" if not model.startswith("models/") else model

        if full_model_name not in model_names:
            raise ValueError(
                f"Model '{model}' not found or doesn't support embeddings. "
                f"Available embedding models: {model_names}"
            )

        logger.info(f"Using embedding model: {full_model_name}")
        return full_model_name

    except Exception as e:
        logger.error(f"Failed to get embedding model: {e}")
        raise


def get_model_info(model_name: Optional[str] = None) -> dict:
    """
    Get information about the configured embedding model

    Args:
        model_name: Model to get info for (optional, uses default)

    Returns:
        Dictionary with model information
    """
    configure_gemini_api()

    model = model_name or settings.GEMINI_MODEL
    full_model_name = f"models/{model}" if not model.startswith("models/") else model

    try:
        # Get model details
        available_models = genai.list_models()
        model_info = next(
            (m for m in available_models if m.name == full_model_name),
            None
        )

        if not model_info:
            raise ValueError(f"Model '{model}' not found")

        return {
            "name": model_info.name,
            "display_name": model_info.display_name,
            "description": model_info.description,
            "supported_methods": model_info.supported_generation_methods,
            "input_token_limit": model_info.input_token_limit,
            "output_token_limit": model_info.output_token_limit,
        }

    except Exception as e:
        logger.error(f"Failed to get model info: {e}")
        return {}


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for text (rough approximation)

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    # Rough estimate: ~4 characters per token for English
    # More accurate would use tokenizer, but this is fast approximation
    return len(text) // 4


def chunk_text_if_needed(
    text: str,
    max_tokens: int = 2000,
    overlap: int = 100
) -> list[str]:
    """
    Split text into chunks if it exceeds max token limit

    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk
        overlap: Number of tokens to overlap between chunks

    Returns:
        List of text chunks
    """
    estimated_tokens = estimate_token_count(text)

    # If text fits in one chunk, return as-is
    if estimated_tokens <= max_tokens:
        return [text]

    # Calculate chunk size in characters (rough estimate)
    chunk_size = max_tokens * 4  # ~4 chars per token
    overlap_size = overlap * 4

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Find sentence boundary to avoid splitting mid-sentence
        if end < len(text):
            # Look for period, exclamation, or question mark
            boundary = max(
                text.rfind('. ', start, end),
                text.rfind('! ', start, end),
                text.rfind('? ', start, end)
            )

            # If found, use it; otherwise use chunk size
            if boundary > start:
                end = boundary + 1

        chunks.append(text[start:end])

        # Move to next chunk with overlap
        start = end - overlap_size

        # Prevent infinite loop
        if start >= len(text):
            break

    logger.info(f"Split text into {len(chunks)} chunks (estimated {estimated_tokens} tokens)")
    return chunks
