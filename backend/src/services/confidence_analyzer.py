"""
Service for analyzing low-confidence compliance rules using LLM.
Uses Groq Kimi K2 with compliance officer persona for comprehensive analysis.
"""

import json
import structlog
from typing import Dict, List, Any
from services.groq_client import create_groq_client, GroqRateLimitError

logger = structlog.get_logger(__name__)


async def analyze_low_confidence(rule: Dict[str, Any], tier: str = "moderate") -> Dict[str, Any]:
    """
    Analyze a low-confidence rule using LLM with compliance officer persona.

    Args:
        rule: Rule dictionary containing rule_type, rule_data, extraction_confidence, etc.
        tier: Confidence tier - "moderate" (80-95%) or "low" (< 80%)

    Returns:
        Dictionary with 'reason' (str) and 'questions' (list[str])
    """
    rule_type = rule.get("rule_type", "unknown")
    rule_data = rule.get("rule_details") or rule.get("rule_data") or {}
    confidence = rule.get("extraction_confidence", 1.0)
    source_text = rule.get("source_text", "")
    jurisdiction = rule.get("jurisdiction", "Unknown")
    regulator = rule.get("regulator", "Unknown")

    try:
        # Use LLM for comprehensive analysis
        groq = create_groq_client()

        # Build prompt
        messages = _build_compliance_analysis_prompt(
            rule_type=rule_type,
            rule_data=rule_data,
            source_text=source_text,
            confidence=confidence,
            tier=tier,
            jurisdiction=jurisdiction,
            regulator=regulator
        )

        # Call LLM with JSON mode
        response_text, metadata = await groq.chat_completion(
            messages=messages,
            temperature=0.3,  # Slightly higher for more creative question generation
            max_tokens=1500,
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        analysis = json.loads(response_text)

        reason = analysis.get("reason", "Confidence level requires additional review.")
        questions = analysis.get("questions", [])

        # Ensure we have at least some questions
        if not questions or len(questions) == 0:
            questions = _get_fallback_questions(rule_type)

        logger.info(
            "LLM confidence analysis completed",
            rule_type=rule_type,
            tier=tier,
            confidence=confidence,
            questions_count=len(questions),
            tokens_used=metadata.get("tokens_used", 0)
        )

        return {
            "reason": reason,
            "questions": questions[:5]  # Limit to 5 questions
        }

    except Exception as e:
        logger.error("LLM analysis failed, using fallback", error=str(e), rule_type=rule_type)
        # Fallback to rule-based analysis
        return _fallback_analysis(rule_type, rule_data, confidence, source_text, tier)


def _build_compliance_analysis_prompt(
    rule_type: str,
    rule_data: Dict[str, Any],
    source_text: str,
    confidence: float,
    tier: str,
    jurisdiction: str,
    regulator: str
) -> List[Dict[str, str]]:
    """Build prompt messages for LLM analysis with compliance officer persona."""

    system_prompt = """You are a senior compliance officer at a major international bank with 15+ years of experience reviewing regulatory circulars and implementing compliance rules.

Your expertise includes:
- Understanding complex regulatory language from various jurisdictions (MAS, HKMA, FCA, etc.)
- Interpreting AML/CFT requirements, transaction reporting thresholds, and enhanced due diligence rules
- Identifying ambiguities or gaps in regulatory text that require clarification
- Formulating precise questions to regulatory authorities

Your task is to review extracted compliance rules from regulatory circulars and provide professional analysis when the extraction confidence is below 95%."""

    # Format rule data for display
    rule_data_str = json.dumps(rule_data, indent=2) if rule_data else "No structured data extracted"

    # Truncate source text if too long (keep first 3000 chars)
    display_source_text = source_text[:3000] + "..." if len(source_text) > 3000 else source_text

    confidence_percentage = round(confidence * 100)
    tier_label = "LOW" if tier == "low" else "MODERATE"

    user_prompt = f"""Please analyze this compliance rule extraction that has {tier_label} confidence ({confidence_percentage}%).

**Context:**
- Jurisdiction: {jurisdiction}
- Regulator: {regulator}
- Rule Type: {rule_type}

**Source Regulatory Text:**
```
{display_source_text}
```

**Extracted Structured Data:**
```json
{rule_data_str}
```

**Your Task:**
As a compliance officer, provide:

1. **Professional Explanation**: Why is the extraction confidence {tier}? What specific aspects of the regulatory text or extracted data are unclear, incomplete, or ambiguous? Use professional compliance language.

2. **Clarification Questions**: Generate exactly 5 specific, actionable questions that you would ask the regulatory authority or internal compliance team to resolve the ambiguity. These should be:
   - Specific to the actual content (not generic)
   - Professionally worded for regulatory correspondence
   - Focused on compliance implementation
   - Practical and answerable

**Response Format (JSON):**
```json
{{
  "reason": "Professional explanation of why confidence is {tier}, specific to this rule and regulatory text...",
  "questions": [
    "Specific question 1?",
    "Specific question 2?",
    "Specific question 3?",
    "Specific question 4?",
    "Specific question 5?"
  ]
}}
```"""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


def _fallback_analysis(
    rule_type: str,
    rule_data: Dict[str, Any],
    confidence: float,
    source_text: str,
    tier: str
) -> Dict[str, Any]:
    """Fallback rule-based analysis if LLM fails."""

    reasons = []

    # Check source text quality
    if tier == "low":
        if not source_text or len(source_text.strip()) < 50:
            reasons.append("source text is severely lacking or unclear")
        elif len(source_text.strip()) < 150:
            reasons.append("source text is insufficient for accurate extraction")
    else:  # moderate
        if not source_text or len(source_text.strip()) < 50:
            reasons.append("source text is too brief")
        elif len(source_text.strip()) < 150:
            reasons.append("source text lacks sufficient detail")

    # Generic fallback
    if not reasons:
        if tier == "low":
            reasons.append("multiple critical details are missing or ambiguous")
        else:
            reasons.append("some key details require clarification")

    confidence_label = "low" if tier == "low" else "moderate"

    if len(reasons) == 1:
        reason = f"The confidence is {confidence_label} because {reasons[0]}."
    else:
        reason = f"The confidence is {confidence_label} because {', '.join(reasons)}."

    questions = _get_fallback_questions(rule_type)

    return {
        "reason": reason,
        "questions": questions
    }


def _get_fallback_questions(rule_type: str) -> List[str]:
    """Get generic fallback questions based on rule type."""

    fallback_questions = {
        "threshold": [
            "What is the exact threshold amount specified in the regulation?",
            "Which currencies or currency equivalents does this threshold apply to?",
            "What is the time period for aggregating transactions?",
            "Are there any exemptions or exceptions to this threshold requirement?",
            "What reporting or notification procedures apply when the threshold is breached?"
        ],
        "deadline": [
            "What is the precise deadline timeframe (in business days or calendar days)?",
            "What specific event triggers the deadline countdown?",
            "What is the required action or filing that must be completed?",
            "Are there any provisions for extensions or grace periods?",
            "What are the consequences of missing this deadline?"
        ],
        "edd_trigger": [
            "What specific category triggers the Enhanced Due Diligence requirement?",
            "What enhanced measures must be applied?",
            "What approval levels are required for establishing or maintaining the relationship?",
            "What is the frequency of periodic reviews for these high-risk relationships?",
            "Are there any specific documentation requirements?"
        ],
        "sanctions": [
            "Which sanctions list(s) must be screened against?",
            "What is the required screening frequency?",
            "What is the minimum match threshold for flagging potential matches?",
            "What is the escalation procedure for potential matches?",
            "Are there any exemptions or safe harbors?"
        ],
        "record_keeping": [
            "What is the required retention period for these records?",
            "What specific types of records or documents must be retained?",
            "What are the storage requirements (electronic, physical, accessible format)?",
            "Are there any specific retrieval or audit requirements?",
            "Under what conditions can records be disposed of earlier?"
        ]
    }

    # Try to match rule type
    for key, questions in fallback_questions.items():
        if key in rule_type.lower():
            return questions

    # Generic fallback
    return [
        "What is the primary regulatory requirement described in this rule?",
        "Which entities or institutions does this requirement apply to?",
        "What are the specific conditions or triggers for compliance?",
        "What are the consequences of non-compliance?",
        "Are there any exemptions or exceptions to this requirement?"
    ]
