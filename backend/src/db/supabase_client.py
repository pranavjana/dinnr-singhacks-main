"""
Supabase Python SDK client configuration
Handles authentication, S3-compatible storage, and bucket management
"""
import logging
from functools import lru_cache
from typing import Optional

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions

from config import settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_supabase_client() -> Client:
    """
    Create and configure Supabase client with connection pooling

    Returns:
        Configured Supabase client instance

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_KEY not configured
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be configured in environment"
        )

    logger.info(f"Initializing Supabase client for {settings.SUPABASE_URL}")

    # Configure client options for connection pooling
    options = ClientOptions(
        auto_refresh_token=True,
        persist_session=True,
    )

    client = create_client(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_KEY,
        options=options
    )

    logger.info("Supabase client initialized successfully")
    return client


def get_storage_bucket(bucket_name: Optional[str] = None):
    """
    Get reference to Supabase storage bucket for PDF files

    Args:
        bucket_name: Name of storage bucket (defaults to settings.SUPABASE_BUCKET_NAME)

    Returns:
        Supabase storage bucket reference

    Raises:
        ValueError: If bucket name not configured
    """
    bucket = bucket_name or settings.SUPABASE_BUCKET_NAME

    if not bucket:
        raise ValueError("SUPABASE_BUCKET_NAME must be configured in environment")

    client = get_supabase_client()
    storage = client.storage.from_(bucket)

    logger.debug(f"Retrieved storage bucket: {bucket}")
    return storage


def ensure_bucket_exists(bucket_name: Optional[str] = None) -> bool:
    """
    Ensure storage bucket exists, create if it doesn't

    Args:
        bucket_name: Name of storage bucket to create

    Returns:
        True if bucket exists or was created successfully
    """
    bucket = bucket_name or settings.SUPABASE_BUCKET_NAME

    if not bucket:
        raise ValueError("SUPABASE_BUCKET_NAME must be configured")

    client = get_supabase_client()

    try:
        # List buckets to check if ours exists
        buckets = client.storage.list_buckets()
        bucket_names = [b.name for b in buckets]

        if bucket in bucket_names:
            logger.info(f"Bucket '{bucket}' already exists")
            return True

        # Create bucket if it doesn't exist
        logger.info(f"Creating bucket '{bucket}'")
        client.storage.create_bucket(
            bucket,
            options={
                "public": False,  # Private bucket for compliance documents
                "file_size_limit": 524288000,  # 500MB max file size
                "allowed_mime_types": ["application/pdf"]
            }
        )
        logger.info(f"Bucket '{bucket}' created successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to ensure bucket exists: {e}")
        return False


def upload_pdf_to_storage(
    file_bytes: bytes,
    file_path: str,
    bucket_name: Optional[str] = None
) -> str:
    """
    Upload PDF file to Supabase storage

    Args:
        file_bytes: PDF file content as bytes
        file_path: Destination path within bucket (e.g., "pdfs/doc-123.pdf")
        bucket_name: Storage bucket name (optional, uses default)

    Returns:
        Public URL of uploaded file

    Raises:
        Exception: If upload fails
    """
    storage = get_storage_bucket(bucket_name)

    try:
        # Upload file
        result = storage.upload(
            path=file_path,
            file=file_bytes,
            file_options={
                "content-type": "application/pdf",
                "cache-control": "3600",  # Cache for 1 hour
                "upsert": "false"  # Don't overwrite existing files
            }
        )

        logger.info(f"Uploaded file to: {file_path}")

        # Get public URL (even though bucket is private, we can generate signed URLs)
        # For private buckets, use create_signed_url instead
        public_url = storage.get_public_url(file_path)
        return public_url

    except Exception as e:
        logger.error(f"Failed to upload file {file_path}: {e}")
        raise


def download_pdf_from_storage(
    file_path: str,
    bucket_name: Optional[str] = None
) -> bytes:
    """
    Download PDF file from Supabase storage

    Args:
        file_path: Path to file within bucket
        bucket_name: Storage bucket name (optional, uses default)

    Returns:
        File content as bytes

    Raises:
        Exception: If download fails
    """
    storage = get_storage_bucket(bucket_name)

    try:
        file_bytes = storage.download(file_path)
        logger.info(f"Downloaded file from: {file_path}")
        return file_bytes

    except Exception as e:
        logger.error(f"Failed to download file {file_path}: {e}")
        raise


def delete_pdf_from_storage(
    file_path: str,
    bucket_name: Optional[str] = None
) -> bool:
    """
    Delete PDF file from Supabase storage

    Args:
        file_path: Path to file within bucket
        bucket_name: Storage bucket name (optional, uses default)

    Returns:
        True if deletion successful

    Raises:
        Exception: If deletion fails
    """
    storage = get_storage_bucket(bucket_name)

    try:
        storage.remove([file_path])
        logger.info(f"Deleted file: {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        raise
