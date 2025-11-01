"""
Structured JSON logging configuration for PDF document processing
Provides consistent logging format across all services
"""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

from config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional fields
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """
        Add custom fields to log record

        Args:
            log_record: Dictionary to add fields to
            record: Original log record
            message_dict: Message dictionary
        """
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Add log level
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname

        # Add service name
        log_record['service'] = 'pdf-document-processing'

        # Add environment
        log_record['environment'] = settings.FASTAPI_ENV

        # Add logger name
        log_record['logger'] = record.name


def setup_logging(
    level: Optional[str] = None,
    json_format: bool = True
) -> None:
    """
    Configure application logging

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON format (default: True)
    """
    log_level = level or settings.LOG_LEVEL or "INFO"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    # Remove existing handlers
    root_logger.handlers = []

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level.upper())

    if json_format:
        # Use JSON formatter for structured logging
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        # Use standard formatter for local development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set log levels for third-party libraries
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    root_logger.info(
        f"Logging configured",
        extra={
            "log_level": log_level,
            "json_format": json_format,
            "environment": settings.FASTAPI_ENV
        }
    )


def log_event(
    logger: logging.Logger,
    event: str,
    level: str = "INFO",
    **context
) -> None:
    """
    Log structured event with context

    Args:
        logger: Logger instance
        event: Event name/type
        level: Log level (default: INFO)
        **context: Additional context fields
    """
    log_method = getattr(logger, level.lower(), logger.info)

    log_method(
        event,
        extra={
            "event": event,
            **context
        }
    )


def log_document_event(
    logger: logging.Logger,
    event: str,
    document_id: str,
    **context
) -> None:
    """
    Log document-related event

    Args:
        logger: Logger instance
        event: Event name
        document_id: Document UUID
        **context: Additional context
    """
    log_event(
        logger,
        event,
        level="INFO",
        document_id=document_id,
        **context
    )


def log_embedding_event(
    logger: logging.Logger,
    event: str,
    document_id: str,
    tokens_used: Optional[int] = None,
    api_latency_ms: Optional[int] = None,
    retry_attempt: Optional[int] = None,
    **context
) -> None:
    """
    Log embedding-related event

    Args:
        logger: Logger instance
        event: Event name
        document_id: Document UUID
        tokens_used: API tokens consumed
        api_latency_ms: API call latency
        retry_attempt: Retry attempt number
        **context: Additional context
    """
    log_event(
        logger,
        event,
        level="INFO",
        document_id=document_id,
        tokens_used=tokens_used,
        api_latency_ms=api_latency_ms,
        retry_attempt=retry_attempt,
        **context
    )


def log_error(
    logger: logging.Logger,
    error: Exception,
    event: str,
    **context
) -> None:
    """
    Log error with full context

    Args:
        logger: Logger instance
        error: Exception that occurred
        event: Event that failed
        **context: Additional context
    """
    logger.error(
        f"{event} failed: {str(error)}",
        extra={
            "event": event,
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context
        },
        exc_info=True
    )


def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **context
) -> None:
    """
    Log API request

    Args:
        logger: Logger instance
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **context: Additional context
    """
    log_event(
        logger,
        "api_request",
        level="INFO",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        **context
    )


# Performance logging helpers

class LogExecutionTime:
    """
    Context manager to log execution time

    Usage:
        with LogExecutionTime(logger, "embedding_generation", document_id="abc"):
            # Code to measure
            generate_embedding()
    """

    def __init__(
        self,
        logger: logging.Logger,
        event: str,
        **context
    ):
        self.logger = logger
        self.event = event
        self.context = context
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = int(
                (datetime.utcnow() - self.start_time).total_seconds() * 1000
            )

            if exc_type is None:
                # Success
                log_event(
                    self.logger,
                    f"{self.event}_completed",
                    level="INFO",
                    duration_ms=duration_ms,
                    **self.context
                )
            else:
                # Failure
                log_error(
                    self.logger,
                    exc_val,
                    f"{self.event}_failed",
                    duration_ms=duration_ms,
                    **self.context
                )

        return False  # Don't suppress exceptions


# Initialize logging on module import
if not settings.IS_TESTING:
    setup_logging()
