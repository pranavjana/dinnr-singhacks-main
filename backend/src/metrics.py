"""
Prometheus metrics collection for PDF document processing
Tracks processing performance, API latency, and error rates
"""
import logging
from functools import wraps
from time import time
from typing import Callable

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)

# Create custom registry
registry = CollectorRegistry()

# Document processing metrics
documents_processed_total = Counter(
    'pdf_documents_processed_total',
    'Total number of PDF documents processed',
    ['status', 'source'],
    registry=registry
)

documents_ingested_total = Counter(
    'pdf_documents_ingested_total',
    'Total number of documents ingested',
    ['source'],
    registry=registry
)

documents_extraction_failed_total = Counter(
    'pdf_documents_extraction_failed_total',
    'Total number of extraction failures',
    ['reason'],
    registry=registry
)

documents_duplicate_total = Counter(
    'pdf_documents_duplicate_total',
    'Total number of duplicate documents detected',
    ['source'],
    registry=registry
)

# Embedding metrics
embeddings_generated_total = Counter(
    'pdf_embeddings_generated_total',
    'Total number of embeddings generated',
    ['model'],
    registry=registry
)

embeddings_failed_total = Counter(
    'pdf_embeddings_failed_total',
    'Total number of embedding failures',
    ['reason', 'retry_attempt'],
    registry=registry
)

embeddings_retried_total = Counter(
    'pdf_embeddings_retried_total',
    'Total number of embedding retries',
    ['attempt'],
    registry=registry
)

embeddings_cost_usd_total = Counter(
    'pdf_embeddings_cost_usd_total',
    'Total cost of embeddings in USD',
    [],
    registry=registry
)

embeddings_tokens_used_total = Counter(
    'pdf_embeddings_tokens_used_total',
    'Total number of API tokens used',
    ['model'],
    registry=registry
)

# Search metrics
search_queries_total = Counter(
    'pdf_search_queries_total',
    'Total number of search queries',
    ['query_type'],
    registry=registry
)

search_results_returned_total = Counter(
    'pdf_search_results_returned_total',
    'Total number of search results returned',
    [],
    registry=registry
)

search_latency_ms = Histogram(
    'pdf_search_latency_ms',
    'Search query latency in milliseconds',
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    registry=registry
)

# API metrics
api_request_duration_ms = Histogram(
    'pdf_api_request_duration_ms',
    'API request duration in milliseconds',
    ['method', 'endpoint', 'status_code'],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
    registry=registry
)

api_requests_total = Counter(
    'pdf_api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

api_errors_total = Counter(
    'pdf_api_errors_total',
    'Total number of API errors',
    ['method', 'endpoint', 'error_type'],
    registry=registry
)

# Background task metrics
celery_tasks_total = Counter(
    'pdf_celery_tasks_total',
    'Total number of Celery tasks',
    ['task_name', 'status'],
    registry=registry
)

celery_task_duration_ms = Histogram(
    'pdf_celery_task_duration_ms',
    'Celery task duration in milliseconds',
    ['task_name'],
    buckets=[100, 500, 1000, 5000, 10000, 30000, 60000, 300000],
    registry=registry
)

# System metrics
active_connections = Gauge(
    'pdf_active_db_connections',
    'Number of active database connections',
    [],
    registry=registry
)

queue_depth = Gauge(
    'pdf_embedding_queue_depth',
    'Number of documents pending embedding',
    [],
    registry=registry
)

retry_queue_depth = Gauge(
    'pdf_retry_queue_depth',
    'Number of documents in retry queue',
    [],
    registry=registry
)


# Metric helper functions

def record_document_ingested(source: str):
    """Record document ingestion"""
    documents_ingested_total.labels(source=source).inc()
    logger.debug(f"Recorded document ingested from {source}")


def record_document_processed(status: str, source: str):
    """Record document processing completion"""
    documents_processed_total.labels(status=status, source=source).inc()
    logger.debug(f"Recorded document processed: {status} from {source}")


def record_extraction_failed(reason: str):
    """Record extraction failure"""
    documents_extraction_failed_total.labels(reason=reason).inc()
    logger.debug(f"Recorded extraction failure: {reason}")


def record_duplicate_detected(source: str):
    """Record duplicate detection"""
    documents_duplicate_total.labels(source=source).inc()
    logger.debug(f"Recorded duplicate from {source}")


def record_embedding_generated(model: str, tokens_used: int, cost_usd: float):
    """Record embedding generation"""
    embeddings_generated_total.labels(model=model).inc()
    embeddings_tokens_used_total.labels(model=model).inc(tokens_used)
    embeddings_cost_usd_total.inc(cost_usd)
    logger.debug(f"Recorded embedding: {tokens_used} tokens, ${cost_usd:.4f}")


def record_embedding_failed(reason: str, retry_attempt: int):
    """Record embedding failure"""
    embeddings_failed_total.labels(reason=reason, retry_attempt=str(retry_attempt)).inc()
    logger.debug(f"Recorded embedding failure: {reason} (attempt {retry_attempt})")


def record_embedding_retry(attempt: int):
    """Record embedding retry"""
    embeddings_retried_total.labels(attempt=str(attempt)).inc()
    logger.debug(f"Recorded embedding retry attempt {attempt}")


def record_search_query(query_type: str, latency_ms: float, result_count: int):
    """Record search query"""
    search_queries_total.labels(query_type=query_type).inc()
    search_latency_ms.observe(latency_ms)
    search_results_returned_total.inc(result_count)
    logger.debug(f"Recorded search: {query_type}, {latency_ms}ms, {result_count} results")


def record_api_request(method: str, endpoint: str, status_code: int, duration_ms: float):
    """Record API request"""
    api_requests_total.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    api_request_duration_ms.labels(method=method, endpoint=endpoint, status_code=str(status_code)).observe(duration_ms)
    logger.debug(f"Recorded API request: {method} {endpoint} {status_code} ({duration_ms}ms)")


def record_api_error(method: str, endpoint: str, error_type: str):
    """Record API error"""
    api_errors_total.labels(method=method, endpoint=endpoint, error_type=error_type).inc()
    logger.debug(f"Recorded API error: {method} {endpoint} ({error_type})")


def record_celery_task(task_name: str, status: str, duration_ms: float):
    """Record Celery task execution"""
    celery_tasks_total.labels(task_name=task_name, status=status).inc()
    celery_task_duration_ms.labels(task_name=task_name).observe(duration_ms)
    logger.debug(f"Recorded Celery task: {task_name} {status} ({duration_ms}ms)")


def update_queue_depths(embedding_queue: int, retry_queue: int):
    """Update queue depth metrics"""
    queue_depth.set(embedding_queue)
    retry_queue_depth.set(retry_queue)


# Decorator for timing functions
def timed_operation(metric_name: str = None):
    """
    Decorator to time function execution and record metric

    Args:
        metric_name: Name for the metric (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time() - start_time) * 1000

                name = metric_name or func.__name__
                logger.debug(f"{name} completed in {duration_ms:.2f}ms")

                return result
            except Exception as e:
                duration_ms = (time() - start_time) * 1000
                logger.error(f"{func.__name__} failed after {duration_ms:.2f}ms: {e}")
                raise

        return wrapper
    return decorator


def get_metrics() -> bytes:
    """
    Get Prometheus metrics in text format

    Returns:
        Metrics in Prometheus exposition format
    """
    return generate_latest(registry)


def get_metrics_content_type() -> str:
    """
    Get content type for metrics response

    Returns:
        Content type string
    """
    return CONTENT_TYPE_LATEST
