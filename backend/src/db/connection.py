"""
Database connection pooling with SQLAlchemy
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool

from config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with connection pooling
# Use QueuePool for production, NullPool for testing
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool if not settings.IS_TESTING else NullPool,
    pool_size=10,  # Maximum number of connections to keep open
    max_overflow=20,  # Maximum overflow connections beyond pool_size
    pool_timeout=30,  # Seconds to wait before timing out
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)


# Register event listener to enable pgvector extension on connect
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """
    Ensure pgvector extension is enabled on new connections
    """
    with dbapi_conn.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        logger.debug("Enabled pgvector extension on connection")


# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent detached instance errors
)


def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session with automatic cleanup

    Usage:
        with get_db_session() as session:
            # Use session
            session.query(Document).all()

    Yields:
        SQLAlchemy session

    Raises:
        Exception: If session creation fails
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


@contextmanager
def get_db():
    """
    Context manager for database sessions (alternative to get_db_session)

    Usage:
        with get_db() as db:
            db.query(Document).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()


def init_db():
    """
    Initialize database connection.

    This function can be called at application startup to ensure
    the database connection is ready.
    """
    try:
        test_connection()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around database operations.

    This is the recommended way to handle database sessions.
    Automatically commits on success, rolls back on exception.

    Usage:
        with session_scope() as session:
            document = Document(...)
            session.add(document)
            # Automatically commits here

    Yields:
        SQLAlchemy Session instance
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction failed: {str(e)}")
        raise
    finally:
        session.close()


def test_connection() -> bool:
    """
    Test database connection

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
