"""
Analyser Node - Extracts structured AML compliance facts from documents.
Feature: 003-langgraph-rule-extraction
"""

import structlog
from datetime import datetime
from typing import Any
from workflows.schemas.extraction_state import ExtractionState
from workflows.prompts.extraction_prompts import build_extraction_prompt, RESULT_KEYS
from services.supabase_service import get_supabase_service
from services.groq_client import create_groq_client, GroqRateLimitError

logger = structlog.get_logger(__name__)


async def analyser_node(state: ExtractionState) -> dict[str, Any]:
    """
    Analyser node: Retrieve document chunks and extract structured compliance facts.

    Processing Steps:
    1. Fetch document and metadata from Supabase
    2. Retrieve embedding chunks (semantic search or full retrieval)
    3. For each target rule type:
       a. Build extraction prompt
       b. Call Groq Kimi K2 for structured extraction
       c. Parse and validate results
    4. Aggregate extracted facts with confidence scores
    5. Update state with results and metrics

    Args:
        state: Current ExtractionState

    Returns:
        Updated state dict with extracted_facts and metrics
    """
    logger.info(
        "Analyser node starting",
        workflow_run_id=state["workflow_run_id"],
        document_id=state["document_id"],
        target_rule_types=state["target_rule_types"]
    )

    db = get_supabase_service()
    groq = create_groq_client()

    errors = []
    extracted_facts = []
    retrieved_chunks = []

    try:
        # Step 1: Fetch document and metadata
        doc_data = await db.get_document_with_metadata(state["document_id"])

        if not doc_data:
            error_msg = f"Document not found: {state['document_id']}"
            logger.error(error_msg)
            return {
                "status": "failed",
                "analyser_errors": [error_msg],
                "current_node": "analyser_failed",
                "retry_count": state.get("retry_count", 0) + 1  # Increment retry count
            }

        # Populate document context in state
        metadata = doc_data.get("metadata", {})
        full_text = doc_data.get("extracted_text", "")

        state_updates = {
            "full_text": full_text,
            "circular_number": metadata.get("circular_number", "Unknown"),
            "issuing_authority": metadata.get("issuing_authority", "Unknown"),
            "effective_date": metadata.get("effective_date"),
            "document_metadata": metadata,
        }

        # Step 2: Retrieve embedding chunks
        # For initial implementation, fetch all chunks ordered by index
        # TODO: Implement semantic search if query embeddings available
        chunks = await db.get_embeddings_for_document(
            state["document_id"],
            limit=None  # Get all chunks
        )

        if not chunks:
            logger.warning("No embedding chunks found, using full text")
            # Fallback: treat full text as single chunk
            chunks = [{
                "id": "full_text",
                "chunk_text": full_text[:50000],  # Limit to 50k chars
                "chunk_index": 0,
                "chunk_start_page": 1,
            }]

        retrieved_chunks = chunks
        logger.info(f"Retrieved {len(chunks)} embedding chunks")

        # Step 3: Extract facts for each rule type
        for rule_type in state["target_rule_types"]:
            logger.info(f"Extracting rule_type: {rule_type}")

            # Combine chunks into coherent text sections
            # Strategy: Group chunks by page ranges for context continuity
            combined_text = _combine_chunks_for_extraction(chunks, max_tokens=100000)

            try:
                # Build extraction prompt
                prompt = build_extraction_prompt(
                    rule_type=rule_type,
                    jurisdiction=state["jurisdiction"],
                    circular_number=state_updates["circular_number"],
                    effective_date=state_updates["effective_date"] or "Not specified",
                    issuing_authority=state_updates["issuing_authority"],
                    regulator=_infer_regulator(state["jurisdiction"]),
                    chunk_text=combined_text,
                    default_currency=_get_default_currency(state["jurisdiction"])
                )

                # Call Groq Kimi K2 with JSON mode
                result_json, api_metadata = await groq.extract_structured_data(
                    system_prompt=prompt,
                    user_content="Extract all rules from the provided document text.",
                    temperature=0.1,
                )

                # Parse extracted rules
                result_key = RESULT_KEYS[rule_type]
                extracted_rules = result_json.get(result_key, [])

                if not extracted_rules:
                    logger.info(f"No {rule_type} rules found in document")
                    continue

                # Validate and package each extracted fact
                for rule_data in extracted_rules:
                    fact = {
                        "rule_type": rule_type,
                        "confidence": rule_data.get("confidence", 0.5),
                        "rule_data": rule_data,
                        "chunk_ids": [c["id"] for c in chunks[:5]],  # Reference source chunks
                        "extraction_metadata": {
                            "tokens_used": api_metadata["total_tokens"],
                            "latency_ms": api_metadata["latency_ms"],
                            "model": api_metadata["model"],
                        }
                    }

                    # Only include high-confidence extractions (>= 0.5)
                    if fact["confidence"] >= 0.5:
                        extracted_facts.append(fact)
                        logger.info(
                            f"Extracted {rule_type} fact",
                            confidence=fact["confidence"],
                            rule_data_preview=str(rule_data)[:200]
                        )
                    else:
                        logger.warning(
                            f"Skipping low-confidence {rule_type} fact",
                            confidence=fact["confidence"]
                        )

                # Update metrics
                state_updates["tokens_used"] = state.get("tokens_used", 0) + api_metadata["total_tokens"]
                state_updates["api_calls"] = state.get("api_calls", 0) + 1

            except GroqRateLimitError as e:
                error_msg = f"Rate limit hit for {rule_type}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Don't fail entire workflow, continue with other rule types

            except Exception as e:
                error_msg = f"Extraction failed for {rule_type}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        # Step 4: Calculate aggregate confidence
        if extracted_facts:
            avg_confidence = sum(f["confidence"] for f in extracted_facts) / len(extracted_facts)
        else:
            avg_confidence = 0.0

        # Calculate cost
        cost_usd = groq.get_total_cost()

        # Step 5: Update state
        final_updates = {
            **state_updates,
            "retrieved_chunks": retrieved_chunks,
            "extracted_facts": extracted_facts,
            "analyser_confidence": avg_confidence,
            "analyser_errors": errors,
            "cost_usd": state.get("cost_usd", 0.0) + cost_usd,
            "current_node": "analyser_completed",
            "status": "partial" if errors else "running",
        }

        logger.info(
            "Analyser node completed",
            facts_extracted=len(extracted_facts),
            avg_confidence=avg_confidence,
            total_tokens=state_updates.get("tokens_used", 0),
            cost_usd=cost_usd,
            errors=len(errors)
        )

        return final_updates

    except Exception as e:
        logger.error("Analyser node failed", error=str(e), exc_info=True)
        return {
            "status": "failed",
            "analyser_errors": [f"Critical error: {str(e)}"],
            "current_node": "analyser_failed",
        }


def _combine_chunks_for_extraction(chunks: list[dict], max_tokens: int = 100000) -> str:
    """
    Combine embedding chunks into coherent text for extraction.

    Args:
        chunks: List of chunk dicts with chunk_text and chunk_index
        max_tokens: Approximate max tokens (chars * 0.3)

    Returns:
        Combined text string
    """
    combined = []
    total_chars = 0
    max_chars = int(max_tokens / 0.3)  # Rough token-to-char ratio

    for chunk in sorted(chunks, key=lambda c: c.get("chunk_index", 0)):
        chunk_text = chunk.get("chunk_text", "")
        if total_chars + len(chunk_text) > max_chars:
            logger.warning(f"Reached max tokens, truncating at {len(combined)} chunks")
            break

        combined.append(chunk_text)
        total_chars += len(chunk_text)

    return "\n\n".join(combined)


def _infer_regulator(jurisdiction: str) -> str:
    """Map jurisdiction code to primary regulator."""
    mapping = {
        "SG": "MAS",
        "HK": "HKMA",
        "MY": "BNM",
        "ID": "OJK",
        "TH": "BOT",
        "PH": "BSP",
    }
    return mapping.get(jurisdiction, "Unknown")


def _get_default_currency(jurisdiction: str) -> str:
    """Get default currency for jurisdiction."""
    mapping = {
        "SG": "SGD",
        "HK": "HKD",
        "MY": "MYR",
        "ID": "IDR",
        "TH": "THB",
        "PH": "PHP",
    }
    return mapping.get(jurisdiction, "USD")
