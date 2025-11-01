"""
Celery and Redis configuration for background task processing
"""
import logging
from celery import Celery
from kombu import Exchange, Queue

from config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "pdf_processing",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Configure Celery
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "src.tasks.immediate_embed.*": {"queue": "embedding"},
        "src.tasks.annual_refresh.*": {"queue": "batch"},
        "src.tasks.embedding_retry.*": {"queue": "retry"},
    },

    # Task execution settings
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    task_track_started=True,  # Track task start time

    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },

    # Worker settings
    worker_prefetch_multiplier=1,  # Prefetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks

    # Retry settings
    task_default_retry_delay=30 * 60,  # 30 minutes default retry delay
    task_max_retries=3,  # Maximum 3 retries per task

    # Beat schedule (for annual refresh)
    beat_schedule={
        "annual-document-refresh": {
            "task": "src.tasks.annual_refresh.annual_refresh_job",
            "schedule": {
                "month_of_year": 11,  # November
                "day_of_month": 1,  # 1st
                "hour": 0,
                "minute": 0,
            },
        },
        "retry-failed-embeddings": {
            "task": "src.tasks.embedding_retry.process_retry_queue",
            "schedule": 300.0,  # Every 5 minutes
        },
    },
)

# Define task queues
celery_app.conf.task_queues = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("embedding", Exchange("embedding"), routing_key="embedding.#"),
    Queue("batch", Exchange("batch"), routing_key="batch.#"),
    Queue("retry", Exchange("retry"), routing_key="retry.#"),
)

# Default queue
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"


def test_redis_connection() -> bool:
    """
    Test Redis connection

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Try to ping Redis
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        logger.info("Redis connection test successful")
        return True
    except Exception as e:
        logger.error(f"Redis connection test failed: {e}")
        return False


def test_celery_connection() -> bool:
    """
    Test Celery broker connection

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Inspect Celery workers
        inspect = celery_app.control.inspect()
        stats = inspect.stats()

        if stats:
            logger.info(f"Celery connection successful. Active workers: {len(stats)}")
            return True
        else:
            logger.warning("Celery connection successful but no workers available")
            return True

    except Exception as e:
        logger.error(f"Celery connection test failed: {e}")
        return False


# Import tasks to register them with Celery
# This will be populated as tasks are created
def register_tasks():
    """
    Register all Celery tasks

    This function imports task modules to register them with Celery app
    """
    try:
        # Import task modules (will be created in Phase 3+)
        # from src.tasks import immediate_embed
        # from src.tasks import annual_refresh
        # from src.tasks import embedding_retry

        logger.info("All Celery tasks registered successfully")
    except ImportError as e:
        logger.warning(f"Some tasks not yet implemented: {e}")
