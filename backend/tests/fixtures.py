"""
Pytest fixtures for testing PDF document processing
"""
import os
import tempfile
from datetime import datetime
from typing import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.models.document import Base, Document, DocumentMetadata, Embedding, ProcessingLog
from src.models.document import (
    ProcessingStatus,
    DocumentType,
    Language,
    ExtractionMethod,
    ValidationStatus,
    EventType,
    EventStatus,
)


# Database Fixtures

@pytest.fixture(scope="session")
def test_database_url():
    """
    Test database URL (uses in-memory SQLite for speed)
    """
    return "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine(test_database_url):
    """
    Create test database engine
    """
    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db_session(test_engine) -> Generator[Session, None, None]:
    """
    Create test database session with automatic rollback
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# Sample PDF Fixtures

@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """
    Generate minimal valid PDF file bytes for testing
    """
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000317 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content


@pytest.fixture
def sample_pdf_file(sample_pdf_bytes) -> Generator[str, None, None]:
    """
    Create temporary PDF file for testing
    """
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.pdf', delete=False) as f:
        f.write(sample_pdf_bytes)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_large_pdf_bytes() -> bytes:
    """
    Generate larger PDF for testing chunking logic
    """
    # Create PDF with multiple pages and more content
    pages_content = []
    for i in range(10):
        pages_content.append(f"Page {i + 1} content. " * 100)

    # This is a simplified structure; real tests should use proper PDF library
    return sample_pdf_bytes()  # Placeholder - extend if needed


# Mock Gemini API Fixtures

@pytest.fixture
def mock_gemini_embedding():
    """
    Mock Gemini API embedding response (768 dimensions)
    """
    import random
    return [random.random() for _ in range(768)]


@pytest.fixture
def mock_gemini_api_success(mocker, mock_gemini_embedding):
    """
    Mock successful Gemini API call
    """
    mock_response = mocker.Mock()
    mock_response.embedding = mock_gemini_embedding

    mock_client = mocker.patch("google.generativeai.embed_content")
    mock_client.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_gemini_api_failure(mocker):
    """
    Mock failed Gemini API call
    """
    mock_client = mocker.patch("google.generativeai.embed_content")
    mock_client.side_effect = Exception("API rate limit exceeded")

    return mock_client


# Test Document Fixtures

@pytest.fixture
def sample_document(test_db_session) -> Document:
    """
    Create sample Document entity for testing
    """
    doc = Document(
        id=uuid4(),
        source_url="https://mas.org.sg/circular-2024-01",
        filename="circular-2024-01.pdf",
        file_hash="abc123def456",
        file_size_bytes=1024000,
        page_count=10,
        extracted_text="Sample extracted text content from MAS circular.",
        ingestion_date=datetime.utcnow(),
        ingestion_source="Monetary Authority of Singapore",
        processing_status=ProcessingStatus.INGESTED,
        extraction_confidence=0.95,
        is_duplicate=False,
        canonical_document_id=None,
    )

    test_db_session.add(doc)
    test_db_session.commit()
    test_db_session.refresh(doc)

    return doc


@pytest.fixture
def sample_document_metadata(test_db_session, sample_document) -> DocumentMetadata:
    """
    Create sample DocumentMetadata for testing
    """
    metadata = DocumentMetadata(
        id=uuid4(),
        document_id=sample_document.id,
        document_type=DocumentType.CIRCULAR,
        effective_date=datetime(2024, 1, 1),
        expiry_date=None,
        regulatory_framework=["AML", "KYC"],
        primary_language=Language.ENGLISH,
        has_chinese_content=False,
        is_encrypted=False,
        ocr_required=False,
        issuing_authority="Monetary Authority of Singapore",
        circular_number="MAS/CIRCULAR/2024-01",
        version="1.0",
        extraction_method=ExtractionMethod.PDFPLUMBER,
        validation_status=ValidationStatus.VALIDATED,
    )

    test_db_session.add(metadata)
    test_db_session.commit()
    test_db_session.refresh(metadata)

    return metadata


@pytest.fixture
def sample_embedding(test_db_session, sample_document, mock_gemini_embedding) -> Embedding:
    """
    Create sample Embedding for testing
    """
    embedding = Embedding(
        id=uuid4(),
        document_id=sample_document.id,
        embedding_vector=mock_gemini_embedding,
        chunk_index=0,
        content_length=512,
        embedding_model="models/embedding-001",
        embedding_model_version="1.0",
        embedding_timestamp=datetime.utcnow(),
        chunk_text="Sample extracted text content from MAS circular.",
        chunk_start_page=1,
        retry_count=0,
        embedding_cost_usd=0.0001,
    )

    test_db_session.add(embedding)
    test_db_session.commit()
    test_db_session.refresh(embedding)

    return embedding


@pytest.fixture
def sample_processing_log(test_db_session, sample_document) -> ProcessingLog:
    """
    Create sample ProcessingLog for testing
    """
    log = ProcessingLog(
        id=uuid4(),
        document_id=sample_document.id,
        event_type=EventType.INGESTED,
        timestamp=datetime.utcnow(),
        processor_version="1.0.0",
        status=EventStatus.SUCCESS,
        error_message=None,
        user_id="test-user-123",
        api_endpoint="/v1/documents/ingest",
    )

    test_db_session.add(log)
    test_db_session.commit()
    test_db_session.refresh(log)

    return log


# Test User Fixtures

@pytest.fixture
def test_user_token():
    """
    Generate test JWT token for API authentication
    """
    import jwt
    from datetime import timedelta

    payload = {
        "sub": "test-user-123",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=24),
        "role": "authenticated",
    }

    # Use test secret key
    token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
    return token


@pytest.fixture
def auth_headers(test_user_token):
    """
    Generate authorization headers for API requests
    """
    return {
        "Authorization": f"Bearer {test_user_token}",
        "Content-Type": "application/json",
    }


# Celery Task Fixtures

@pytest.fixture
def mock_celery_task(mocker):
    """
    Mock Celery task execution
    """
    mock_task = mocker.patch("celery.app.task.Task.apply_async")
    mock_task.return_value.id = "test-task-id-123"
    return mock_task


# Redis Fixtures

@pytest.fixture
def mock_redis_client(mocker):
    """
    Mock Redis client for testing
    """
    mock_redis = mocker.Mock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    mocker.patch("redis.from_url", return_value=mock_redis)

    return mock_redis


# Supabase Fixtures

@pytest.fixture
def mock_supabase_client(mocker):
    """
    Mock Supabase client for testing
    """
    mock_client = mocker.Mock()

    # Mock storage operations
    mock_storage = mocker.Mock()
    mock_storage.upload.return_value = {"Key": "test-file.pdf"}
    mock_storage.download.return_value = b"test pdf bytes"
    mock_storage.get_public_url.return_value = "https://storage.example.com/test.pdf"

    mock_client.storage.from_.return_value = mock_storage

    mocker.patch("src.db.supabase_client.get_supabase_client", return_value=mock_client)

    return mock_client


# Configuration Fixtures

@pytest.fixture(autouse=True)
def test_environment_variables(monkeypatch):
    """
    Set test environment variables (auto-used for all tests)
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("SUPABASE_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "embedding-001")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("FASTAPI_ENV", "testing")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("IS_TESTING", "true")
