"""
Supabase service layer for compliance rule extraction workflow.
Feature: 003-langgraph-rule-extraction
"""

import asyncio
from typing import Any
from datetime import datetime
import structlog
from supabase import create_client, Client
from config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class SupabaseService:
    """
    Async wrapper around Supabase client for rule extraction operations.

    Provides type-safe methods for querying embeddings, documents,
    and CRUD operations on compliance_rules tables.
    """

    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY  # Use the actual field, not the property
        )

    # Document & Embedding Queries

    async def get_document_with_metadata(self, document_id: str) -> dict | None:
        """
        Fetch document and its metadata in a single query.

        Args:
            document_id: UUID of document

        Returns:
            Combined document and metadata dict, or None if not found
        """
        try:
            # Fetch document
            doc_response = await asyncio.to_thread(
                lambda: self.client.table("documents")
                .select("*")
                .eq("id", document_id)
                .single()
                .execute()
            )

            if not doc_response.data:
                return None

            # Fetch metadata (may not exist for all documents)
            try:
                meta_response = await asyncio.to_thread(
                    lambda: self.client.table("document_metadata")
                    .select("*")
                    .eq("document_id", document_id)
                    .execute()
                )
                metadata = meta_response.data[0] if meta_response.data else {}
            except Exception as e:
                logger.warning(f"No metadata found for document {document_id}: {e}")
                metadata = {}

            return {
                **doc_response.data,
                "metadata": metadata
            }

        except Exception as e:
            logger.error("Failed to fetch document", document_id=document_id, error=str(e))
            return None

    async def get_embeddings_for_document(
        self,
        document_id: str,
        limit: int | None = None
    ) -> list[dict]:
        """
        Retrieve all embedding chunks for a document, ordered by chunk_index.

        Args:
            document_id: UUID of document
            limit: Optional limit on number of chunks

        Returns:
            List of embedding records with chunk_text and metadata
        """
        try:
            query = (
                self.client.table("embeddings")
                .select("id, chunk_text, chunk_index, chunk_start_page, content_length, embedding_vector")
                .eq("document_id", document_id)
                .order("chunk_index", desc=False)
            )

            if limit:
                query = query.limit(limit)

            response = await asyncio.to_thread(query.execute)
            return response.data or []

        except Exception as e:
            logger.error("Failed to fetch embeddings", document_id=document_id, error=str(e))
            return []

    async def semantic_search_chunks(
        self,
        document_id: str,
        query_embedding: list[float],
        top_k: int = 10,
        similarity_threshold: float = 0.7
    ) -> list[dict]:
        """
        Perform semantic search on embedding chunks using vector similarity.

        Args:
            document_id: UUID of document
            query_embedding: Query vector (from embedding search query text)
            top_k: Number of top results to return
            similarity_threshold: Minimum cosine similarity (0-1)

        Returns:
            List of matching chunks with similarity scores
        """
        try:
            # Supabase pgvector similarity search
            response = await asyncio.to_thread(
                lambda: self.client.rpc(
                    "match_embeddings",
                    {
                        "query_embedding": query_embedding,
                        "match_count": top_k,
                        "filter_document_id": document_id,
                        "similarity_threshold": similarity_threshold
                    }
                ).execute()
            )

            return response.data or []

        except Exception as e:
            logger.warning(
                "Semantic search failed, falling back to full chunks",
                document_id=document_id,
                error=str(e)
            )
            # Fallback: return all chunks if similarity search fails
            return await self.get_embeddings_for_document(document_id, limit=top_k)

    # Compliance Rules CRUD

    async def create_compliance_rule(self, rule_data: dict) -> str | None:
        """
        Insert a new compliance rule.

        Args:
            rule_data: Dict matching compliance_rules table schema

        Returns:
            UUID of created rule, or None on failure
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.client.table("compliance_rules")
                .insert(rule_data)
                .execute()
            )

            if response.data and len(response.data) > 0:
                rule_id = response.data[0]["id"]
                logger.info("Created compliance rule", rule_id=rule_id, rule_type=rule_data.get("rule_type"))
                return rule_id

            return None

        except Exception as e:
            logger.error("Failed to create compliance rule", error=str(e), rule_data=rule_data)
            return None

    async def find_duplicate_rules(
        self,
        jurisdiction: str,
        rule_type: str,
        rule_data_fragment: dict,
        active_only: bool = True
    ) -> list[dict]:
        """
        Find potentially duplicate or superseded rules.

        Args:
            jurisdiction: Jurisdiction code (e.g., 'SG')
            rule_type: Rule type (e.g., 'threshold')
            rule_data_fragment: JSONB fragment to search for
            active_only: Only return is_active=true rules

        Returns:
            List of matching rules, ordered by effective_date DESC
        """
        try:
            query = (
                self.client.table("compliance_rules")
                .select("*")
                .eq("jurisdiction", jurisdiction)
                .eq("rule_type", rule_type)
            )

            if active_only:
                query = query.eq("is_active", True)

            # JSONB containment search
            query = query.contains("rule_data", rule_data_fragment)
            query = query.order("effective_date", desc=True).limit(5)

            response = await asyncio.to_thread(query.execute)
            return response.data or []

        except Exception as e:
            logger.error("Failed to search for duplicates", error=str(e))
            return []

    async def update_rule_active_status(self, rule_id: str, is_active: bool) -> bool:
        """
        Update is_active flag for a rule (used in supersession).

        Args:
            rule_id: UUID of rule to update
            is_active: New active status

        Returns:
            True if successful
        """
        try:
            await asyncio.to_thread(
                lambda: self.client.table("compliance_rules")
                .update({"is_active": is_active, "updated_at": datetime.utcnow().isoformat()})
                .eq("id", rule_id)
                .execute()
            )

            logger.info("Updated rule active status", rule_id=rule_id, is_active=is_active)
            return True

        except Exception as e:
            logger.error("Failed to update rule status", rule_id=rule_id, error=str(e))
            return False

    # Audit & Metrics

    async def log_extraction_attempt(self, extraction_data: dict) -> str | None:
        """
        Log extraction attempt to rule_extractions audit table.

        Args:
            extraction_data: Dict matching rule_extractions schema

        Returns:
            UUID of log entry
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.client.table("rule_extractions")
                .insert(extraction_data)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]["id"]

            return None

        except Exception as e:
            logger.error("Failed to log extraction attempt", error=str(e))
            return None

    async def log_workflow_metrics(self, metrics_data: dict) -> str | None:
        """
        Log workflow metrics to extraction_metrics table.

        Args:
            metrics_data: Dict matching extraction_metrics schema

        Returns:
            UUID of metrics entry
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.client.table("extraction_metrics")
                .insert(metrics_data)
                .execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]["id"]

            return None

        except Exception as e:
            logger.error("Failed to log workflow metrics", error=str(e))
            return None

    async def get_recent_extractions(
        self,
        document_id: str | None = None,
        limit: int = 10
    ) -> list[dict]:
        """
        Fetch recent extraction attempts for monitoring.

        Args:
            document_id: Optional filter by document
            limit: Max results

        Returns:
            List of rule_extractions records
        """
        try:
            query = (
                self.client.table("rule_extractions")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
            )

            if document_id:
                query = query.eq("document_id", document_id)

            response = await asyncio.to_thread(query.execute)
            return response.data or []

        except Exception as e:
            logger.error("Failed to fetch recent extractions", error=str(e))
            return []


# Singleton instance
_supabase_service: SupabaseService | None = None


def get_supabase_service() -> SupabaseService:
    """Get or create SupabaseService singleton."""
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service
