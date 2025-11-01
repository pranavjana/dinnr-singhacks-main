"""
Observability module with basic logging and Prometheus metrics.
Provides simple logging and performance metrics collection.
"""
import logging
import sys
from typing import Any, Dict

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

try:
    # Try backend-prefixed imports first (running from parent directory)
    from backend.core.config import settings
except ModuleNotFoundError:
    # Fall back to relative imports (running from backend directory)
    from core.config import settings


# Configure basic logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


# Prometheus metrics registry
registry = CollectorRegistry()

# Payment analysis metrics
payment_analysis_total = Counter(
    "aml_payment_analysis_total",
    "Total number of payment analyses",
    ["verdict", "team"],
    registry=registry
)

analysis_latency_ms = Histogram(
    "aml_analysis_latency_ms",
    "Payment analysis latency in milliseconds",
    buckets=[50, 100, 200, 300, 400, 500, 750, 1000, 1500, 2000, 3000],
    registry=registry
)

patterns_detected_total = Counter(
    "aml_patterns_detected_total",
    "Total number of patterns detected",
    ["pattern_type"],
    registry=registry
)

rules_triggered_total = Counter(
    "aml_rules_triggered_total",
    "Total number of rules triggered",
    ["rule_type"],
    registry=registry
)

active_analyses_gauge = Gauge(
    "aml_active_analyses",
    "Number of currently active payment analyses",
    registry=registry
)

groq_api_calls_total = Counter(
    "groq_api_calls_total",
    "Total number of Groq API calls",
    ["status"],
    registry=registry
)

groq_api_latency_ms = Histogram(
    "groq_api_latency_ms",
    "Groq API latency in milliseconds",
    buckets=[100, 250, 500, 1000, 2000, 5000, 10000],
    registry=registry
)

database_query_latency_ms = Histogram(
    "database_query_latency_ms",
    "Database query latency in milliseconds",
    ["query_type"],
    buckets=[10, 25, 50, 100, 250, 500, 1000],
    registry=registry
)


def get_metrics() -> bytes:
    """
    Generate Prometheus metrics in OpenMetrics format.
    
    Returns:
        bytes: Metrics in Prometheus exposition format
    """
    return generate_latest(registry)


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


# Logging helpers
logger = get_logger(__name__)


def log_analysis_start(trace_id: str, payment_id: str) -> None:
    """Log the start of payment analysis."""
    logger.info(f"payment_analysis_started - trace_id={trace_id}, payment_id={payment_id}")


def log_analysis_complete(
    trace_id: str,
    payment_id: str,
    verdict: str,
    team: str,
    duration_ms: int
) -> None:
    """Log the completion of payment analysis."""
    logger.info(
        f"payment_analysis_completed - trace_id={trace_id}, payment_id={payment_id}, "
        f"verdict={verdict}, team={team}, duration_ms={duration_ms}"
    )

    # Update metrics
    payment_analysis_total.labels(verdict=verdict, team=team).inc()
    analysis_latency_ms.observe(duration_ms)


def log_pattern_detected(
    trace_id: str,
    payment_id: str,
    pattern_type: str,
    confidence: float
) -> None:
    """Log pattern detection."""
    logger.info(
        f"pattern_detected - trace_id={trace_id}, payment_id={payment_id}, "
        f"pattern_type={pattern_type}, confidence={confidence}"
    )

    # Update metrics
    patterns_detected_total.labels(pattern_type=pattern_type).inc()


def log_rule_triggered(
    trace_id: str,
    payment_id: str,
    rule_type: str,
    rule_id: str
) -> None:
    """Log rule trigger."""
    logger.info(
        f"rule_triggered - trace_id={trace_id}, payment_id={payment_id}, "
        f"rule_type={rule_type}, rule_id={rule_id}"
    )

    # Update metrics
    rules_triggered_total.labels(rule_type=rule_type).inc()


def log_error(
    trace_id: str,
    error_type: str,
    error_message: str,
    context: Dict[str, Any] = None
) -> None:
    """Log an error with context."""
    logger.error(
        f"error_occurred - trace_id={trace_id}, error_type={error_type}, "
        f"error_message={error_message}, context={context or {}}"
    )
