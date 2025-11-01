"""Observability helpers (logging + Prometheus metrics)."""

from __future__ import annotations

import hashlib
import logging
import structlog
from prometheus_client import Counter, Histogram


REQUEST_LATENCY = Histogram(
    "aml_triage_request_seconds",
    "Latency per endpoint",
    labelnames=("endpoint",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

LLM_TOKENS = Counter(
    "aml_triage_llm_tokens_total",
    "Token usage reported by Groq responses",
    labelnames=("model_id", "token_type"),
)


def configure_logging() -> None:
    """Initialise structlog for JSON output."""

    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def mask_identifier(value: str | None) -> str | None:
    if not value:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"hash:{digest[:12]}"


__all__ = ["configure_logging", "mask_identifier", "REQUEST_LATENCY", "LLM_TOKENS"]
