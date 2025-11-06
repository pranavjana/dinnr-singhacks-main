"""
Rules Tool Node - Normalizes, deduplicates, and persists compliance rules.
Feature: 003-langgraph-rule-extraction
"""

import structlog
from datetime import datetime
from typing import Any
from difflib import SequenceMatcher
from workflows.schemas.extraction_state import ExtractionState
from workflows.schemas.rule_schemas import validate_rule_data, NormalizedRule
from services.supabase_service import get_supabase_service

logger = structlog.get_logger(__name__)


async def rules_tool_node(state: ExtractionState) -> dict[str, Any]:
    """
    Rules Tool node: Normalize extracted facts and persist to database.

    Processing Steps:
    1. Validate extracted facts against Pydantic schemas
    2. Check for duplicate rules in database
    3. Determine versioning/supersession logic
    4. Normalize facts into compliance_rules format
    5. Write to database
    6. Log audit trail to rule_extractions

    Args:
        state: Current ExtractionState with extracted_facts

    Returns:
        Updated state dict with rule_ids_created/updated
    """
    logger.info(
        "Rules Tool node starting",
        workflow_run_id=state["workflow_run_id"],
        facts_to_process=len(state.get("extracted_facts", []))
    )

    db = get_supabase_service()

    rule_ids_created = []
    rule_ids_updated = []
    normalized_rules = []
    dedup_summary = {
        "duplicates_found": 0,
        "rules_superseded": 0,
        "new_rules_created": 0,
        "validation_failures": 0,
    }

    extracted_facts = state.get("extracted_facts", [])

    if not extracted_facts:
        logger.warning("No extracted facts to process")
        return {
            "status": "completed",
            "current_node": "rules_tool_completed",
            "normalized_rules": [],
            "deduplication_summary": dedup_summary,
        }

    try:
        for fact in extracted_facts:
            rule_type = fact["rule_type"]
            confidence = fact["confidence"]
            raw_rule_data = fact["rule_data"]

            logger.info(f"Processing {rule_type} fact", confidence=confidence)

            # Step 1: Validate rule_data against Pydantic schema
            try:
                validated_rule_data = validate_rule_data(rule_type, raw_rule_data)
            except Exception as e:
                logger.error(
                    "Rule validation failed",
                    rule_type=rule_type,
                    error=str(e),
                    rule_data=raw_rule_data
                )
                dedup_summary["validation_failures"] += 1
                continue

            # Step 2: Build normalized rule
            normalized_rule = NormalizedRule(
                rule_type=rule_type,
                jurisdiction=state["jurisdiction"],
                regulator=_infer_regulator(state["jurisdiction"]),
                rule_schema_version="v1",
                rule_data=validated_rule_data,
                circular_number=state.get("circular_number"),
                effective_date=_parse_effective_date(state.get("effective_date")),
                expiry_date=None,
                source_document_id=state["document_id"],
                extraction_confidence=confidence,
                extraction_model="moonshotai/kimi-k2-instruct-0905",
                validation_status="pending" if confidence <= 0.95 else "validated",
            )

            # Step 3: Check for duplicates
            duplicate_check_fragment = _build_dedup_fragment(validated_rule_data, rule_type)
            existing_rules = await db.find_duplicate_rules(
                jurisdiction=state["jurisdiction"],
                rule_type=rule_type,
                rule_data_fragment=duplicate_check_fragment,
                active_only=True
            )

            # Step 4: Deduplication logic
            if existing_rules:
                is_duplicate, should_supersede = _analyze_duplicates(
                    normalized_rule,
                    existing_rules,
                    validated_rule_data
                )

                if is_duplicate:
                    logger.info(
                        "Duplicate rule found, skipping",
                        rule_type=rule_type,
                        existing_rule_id=existing_rules[0]["id"]
                    )
                    dedup_summary["duplicates_found"] += 1
                    continue

                if should_supersede:
                    # Mark old rule as inactive
                    old_rule_id = existing_rules[0]["id"]
                    await db.update_rule_active_status(old_rule_id, is_active=False)
                    rule_ids_updated.append(old_rule_id)
                    dedup_summary["rules_superseded"] += 1
                    logger.info("Superseded old rule", old_rule_id=old_rule_id)

            # Step 5: Insert new rule
            rule_dict = normalized_rule.model_dump()

            # Convert datetime objects to ISO strings for Supabase
            if rule_dict.get("effective_date"):
                rule_dict["effective_date"] = rule_dict["effective_date"].isoformat()
            if rule_dict.get("expiry_date"):
                rule_dict["expiry_date"] = rule_dict["expiry_date"].isoformat()

            rule_id = await db.create_compliance_rule(rule_dict)

            if rule_id:
                rule_ids_created.append(rule_id)
                normalized_rules.append(rule_dict)
                dedup_summary["new_rules_created"] += 1
                logger.info("Created new compliance rule", rule_id=rule_id, rule_type=rule_type)
            else:
                logger.error("Failed to create rule", rule_type=rule_type)

        # Step 6: Log extraction audit trail
        extraction_audit = {
            "workflow_run_id": state["workflow_run_id"],
            "document_id": state["document_id"],
            "embedding_chunks": [c["id"] for c in state.get("retrieved_chunks", [])[:10]],
            "prompt_template": "rule_extraction_v1",
            "model_parameters": {
                "temperature": 0.1,
                "model": "moonshotai/kimi-k2-instruct-0905"
            },
            "extracted_facts": extracted_facts,
            "created_rules": rule_ids_created,
            "tokens_used": state.get("tokens_used", 0),
            "api_latency_ms": 0,  # TODO: aggregate from individual calls
            "extraction_cost_usd": state.get("cost_usd", 0.0),
            "status": "success" if rule_ids_created else "partial",
            "error_message": None,
            "retry_count": state.get("retry_count", 0),
        }

        await db.log_extraction_attempt(extraction_audit)

        # Step 7: Update state
        logger.info(
            "Rules Tool node completed",
            rules_created=len(rule_ids_created),
            rules_updated=len(rule_ids_updated),
            deduplication_summary=dedup_summary
        )

        return {
            "normalized_rules": normalized_rules,
            "rule_ids_created": rule_ids_created,
            "rule_ids_updated": rule_ids_updated,
            "deduplication_summary": dedup_summary,
            "current_node": "rules_tool_completed",
            "status": "completed",
            "end_time": datetime.utcnow(),
        }

    except Exception as e:
        logger.error("Rules Tool node failed", error=str(e), exc_info=True)
        return {
            "status": "failed",
            "current_node": "rules_tool_failed",
            "end_time": datetime.utcnow(),
        }


def _build_dedup_fragment(rule_data: dict, rule_type: str) -> dict:
    """
    Build JSONB fragment for duplicate detection.

    Returns a subset of rule_data fields that identify uniqueness.
    """
    if rule_type == "threshold":
        return {
            "threshold_type": rule_data.get("threshold_type"),
            "amount": rule_data.get("amount"),
            "currency": rule_data.get("currency"),
        }
    elif rule_type == "deadline":
        return {
            "filing_type": rule_data.get("filing_type"),
            "deadline_days": rule_data.get("deadline_days"),
        }
    elif rule_type == "edd_trigger":
        return {
            "trigger_category": rule_data.get("trigger_category"),
        }
    else:
        # Generic: use first 3 keys
        keys = list(rule_data.keys())[:3]
        return {k: rule_data.get(k) for k in keys}


def _analyze_duplicates(
    new_rule: NormalizedRule,
    existing_rules: list[dict],
    new_rule_data: dict
) -> tuple[bool, bool]:
    """
    Analyze if new rule is duplicate or supersedes existing rules.

    Args:
        new_rule: Normalized rule being inserted
        existing_rules: List of potentially duplicate rules from DB
        new_rule_data: Validated rule_data dict

    Returns:
        Tuple of (is_duplicate, should_supersede)
    """
    if not existing_rules:
        return False, False

    # Compare with most recent existing rule
    most_recent = existing_rules[0]
    existing_data = most_recent.get("rule_data", {})

    # Calculate similarity
    similarity = _calculate_rule_similarity(new_rule_data, existing_data)

    # Duplicate threshold: >95% similar
    if similarity > 0.95:
        return True, False

    # Supersession logic: same circular series but newer effective date
    if (new_rule.circular_number and most_recent.get("circular_number") and
        _is_same_circular_series(new_rule.circular_number, most_recent["circular_number"])):

        new_date = new_rule.effective_date
        old_date = most_recent.get("effective_date")

        if new_date and old_date:
            # Parse if string
            if isinstance(old_date, str):
                old_date = datetime.fromisoformat(old_date.replace("Z", "+00:00"))

            if new_date > old_date:
                return False, True  # Not duplicate, but supersedes

    return False, False


def _calculate_rule_similarity(rule_data_1: dict, rule_data_2: dict) -> float:
    """
    Calculate similarity between two rule_data dicts.

    Uses string similarity on JSON serialization (simple but effective).

    Returns:
        Similarity score 0.0-1.0
    """
    import json

    str1 = json.dumps(rule_data_1, sort_keys=True)
    str2 = json.dumps(rule_data_2, sort_keys=True)

    return SequenceMatcher(None, str1, str2).ratio()


def _is_same_circular_series(circular1: str, circular2: str) -> bool:
    """
    Check if two circular numbers are from same series.

    Example: "MAS Notice 626" and "MAS Notice 626 (Amendment 2023)" → True
    """
    # Extract base number
    base1 = circular1.split("(")[0].strip()
    base2 = circular2.split("(")[0].strip()

    return base1 == base2


def _parse_effective_date(date_str: str | None) -> datetime | None:
    """Parse effective_date string to datetime."""
    if not date_str:
        return None

    try:
        # Try ISO format first
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        # Could add more date parsing logic here
        return None


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
