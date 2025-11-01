"""Initial schema with all tables and pgvector extension

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-11-01 00:00:00.000000

This migration creates:
- pgvector extension for vector similarity search
- documents table (core entity)
- document_metadata table (structured metadata)
- embeddings table (semantic vectors with HNSW index)
- processing_logs table (immutable audit trail)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=False),
        sa.Column('filename', sa.String(length=512), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('ingestion_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ingestion_source', sa.String(length=256), nullable=False),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_status', sa.Enum(
            'ingested', 'pending_embedding', 'embedding_complete', 'embedding_failed',
            name='processingstatus'
        ), nullable=False),
        sa.Column('extraction_confidence', sa.Float(), nullable=False),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False),
        sa.Column('canonical_document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['canonical_document_id'], ['documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_url'),
        sa.UniqueConstraint('file_hash')
    )

    # Create indexes for documents table
    op.create_index('ix_documents_source_url', 'documents', ['source_url'])
    op.create_index('ix_documents_file_hash', 'documents', ['file_hash'])
    op.create_index('ix_documents_ingestion_date', 'documents', ['ingestion_date'])
    op.create_index('ix_documents_processing_status', 'documents', ['processing_status'])

    # Create document_metadata table
    op.create_table(
        'document_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.Enum(
            'circular', 'notice', 'guideline', 'policy', 'other',
            name='documenttype'
        ), nullable=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('regulatory_framework', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('primary_language', sa.Enum(
            'english', 'chinese', 'multilingual',
            name='language'
        ), nullable=False),
        sa.Column('has_chinese_content', sa.Boolean(), nullable=False),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False),
        sa.Column('ocr_required', sa.Boolean(), nullable=False),
        sa.Column('issuing_authority', sa.String(length=512), nullable=False),
        sa.Column('circular_number', sa.String(length=128), nullable=True),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('extraction_method', sa.Enum(
            'pdfplumber', 'pypdf_fallback', 'manual_upload',
            name='extractionmethod'
        ), nullable=False),
        sa.Column('validation_status', sa.Enum(
            'validated', 'requires_review', 'validation_failed',
            name='validationstatus'
        ), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )

    # Create index for regulatory framework filtering (GIN index for array)
    op.create_index(
        'ix_document_metadata_regulatory_framework',
        'document_metadata',
        ['regulatory_framework'],
        postgresql_using='gin'
    )

    # Create embeddings table
    op.create_table(
        'embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('embedding_vector', Vector(768), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content_length', sa.Integer(), nullable=False),
        sa.Column('embedding_model', sa.String(length=128), nullable=False),
        sa.Column('embedding_model_version', sa.String(length=64), nullable=False),
        sa.Column('embedding_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_start_page', sa.Integer(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('embedding_cost_usd', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for embeddings table
    op.create_index('ix_embeddings_document_id', 'embeddings', ['document_id'])
    op.create_index('ix_embeddings_chunk_index', 'embeddings', ['document_id', 'chunk_index'])

    # Create HNSW index for vector similarity search (pgvector)
    # Using cosine distance for semantic similarity
    op.execute(
        'CREATE INDEX ix_embeddings_vector_hnsw ON embeddings '
        'USING hnsw (embedding_vector vector_cosine_ops)'
    )

    # Create processing_logs table (immutable audit trail)
    op.create_table(
        'processing_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.Enum(
            'ingested', 'extraction_started', 'extraction_completed', 'extraction_failed',
            'dedup_check', 'embedding_queued', 'embedding_started', 'embedding_completed',
            'embedding_failed', 'embedding_retried',
            name='eventtype'
        ), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processor_version', sa.String(length=64), nullable=False),
        sa.Column('status', sa.Enum(
            'success', 'partial_success', 'failure',
            name='eventstatus'
        ), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('embedding_model', sa.String(length=128), nullable=True),
        sa.Column('embedding_model_version', sa.String(length=64), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('api_latency_ms', sa.Integer(), nullable=True),
        sa.Column('retry_attempt', sa.Integer(), nullable=True),
        sa.Column('retry_next_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.String(length=128), nullable=True),
        sa.Column('api_endpoint', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for processing_logs table
    op.create_index('ix_processing_logs_document_id', 'processing_logs', ['document_id'])
    op.create_index('ix_processing_logs_timestamp', 'processing_logs', ['timestamp'])

    # Add database-level constraint to enforce audit trail immutability
    # This prevents UPDATE and DELETE operations on processing_logs
    # Note: This is enforced at application level, but can add trigger if needed


def downgrade() -> None:
    # Drop all indexes
    op.drop_index('ix_processing_logs_timestamp', table_name='processing_logs')
    op.drop_index('ix_processing_logs_document_id', table_name='processing_logs')
    op.drop_index('ix_embeddings_chunk_index', table_name='embeddings')
    op.drop_index('ix_embeddings_document_id', table_name='embeddings')
    op.execute('DROP INDEX IF EXISTS ix_embeddings_vector_hnsw')
    op.drop_index('ix_document_metadata_regulatory_framework', table_name='document_metadata')
    op.drop_index('ix_documents_processing_status', table_name='documents')
    op.drop_index('ix_documents_ingestion_date', table_name='documents')
    op.drop_index('ix_documents_file_hash', table_name='documents')
    op.drop_index('ix_documents_source_url', table_name='documents')

    # Drop all tables
    op.drop_table('processing_logs')
    op.drop_table('embeddings')
    op.drop_table('document_metadata')
    op.drop_table('documents')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS eventstatus')
    op.execute('DROP TYPE IF EXISTS eventtype')
    op.execute('DROP TYPE IF EXISTS validationstatus')
    op.execute('DROP TYPE IF EXISTS extractionmethod')
    op.execute('DROP TYPE IF EXISTS language')
    op.execute('DROP TYPE IF EXISTS documenttype')
    op.execute('DROP TYPE IF EXISTS processingstatus')

    # Drop pgvector extension (optional - may want to keep for other features)
    # op.execute('DROP EXTENSION IF EXISTS vector')
