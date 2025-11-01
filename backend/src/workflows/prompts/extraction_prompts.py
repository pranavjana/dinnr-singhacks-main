"""
Prompt templates for AML compliance rule extraction.
Feature: 003-langgraph-rule-extraction
"""

THRESHOLD_EXTRACTION_PROMPT = """You are an expert AML compliance analyst specializing in {jurisdiction} financial regulations.

# Document Context
Circular Number: {circular_number}
Effective Date: {effective_date}
Issuing Authority: {issuing_authority}
Regulator: {regulator}

# Text to Analyze
{chunk_text}

# Task
Extract ALL transaction reporting thresholds mentioned in this text.

For each threshold, provide complete structured data following this exact JSON schema:

{{
  "thresholds": [
    {{
      "threshold_type": "transaction_reporting | ctr | str | cash_transaction",
      "amount": <numeric value>,
      "currency": "SGD|USD|EUR|GBP|HKD|MYR",
      "transaction_type": "cash_deposit|wire_transfer|virtual_asset|other",
      "applies_to": ["list", "of", "entity", "types"],
      "conditions": ["triggering", "conditions"],
      "exemptions": ["exemption", "categories"],
      "source_text": "exact verbatim quote from document",
      "page_reference": <page number or null>,
      "confidence": <0.0 to 1.0>
    }}
  ]
}}

# Extraction Guidelines
1. ONLY extract EXPLICITLY stated thresholds - do not infer or assume
2. Include the exact source quote for audit purposes
3. If currency is not stated, use {default_currency}
4. Mark confidence < 0.7 if information is ambiguous or partially stated
5. For linked transactions, capture the aggregation condition
6. Return empty array if NO thresholds are found
7. Be thorough - extract all thresholds even if similar

# Confidence Scoring
- 1.0: Threshold explicitly stated with all details
- 0.8: Threshold clear but some details implied
- 0.6: Threshold mentioned but conditions unclear
- 0.4: Threshold possibly referenced indirectly
- < 0.3: Do not include

Output ONLY valid JSON. No additional text."""


DEADLINE_EXTRACTION_PROMPT = """You are an expert AML compliance analyst specializing in {jurisdiction} regulatory deadlines.

# Document Context
Circular Number: {circular_number}
Effective Date: {effective_date}
Issuing Authority: {issuing_authority}
Regulator: {regulator}

# Text to Analyze
{chunk_text}

# Task
Extract ALL regulatory filing and reporting deadlines mentioned in this text.

For each deadline, provide complete structured data:

{{
  "deadlines": [
    {{
      "filing_type": "suspicious_transaction_report | currency_transaction_report | annual_aml_return | other",
      "deadline_days": <integer>,
      "deadline_business_days": true|false,
      "trigger_event": "description of what triggers the deadline",
      "penalties": "description of non-compliance penalties or null",
      "applies_to": ["entity", "types"],
      "source_text": "exact quote",
      "page_reference": <int or null>,
      "confidence": <0.0 to 1.0>
    }}
  ]
}}

# Extraction Guidelines
1. Extract calendar days AND business days separately if both mentioned
2. Clearly identify the trigger event (e.g., "knowledge of suspicion", "transaction date")
3. Include penalties if stated
4. Mark confidence < 0.7 if deadline calculation is complex or unclear
5. Return empty array if NO deadlines found

Output ONLY valid JSON."""


EDD_TRIGGER_EXTRACTION_PROMPT = """You are an expert AML compliance analyst specializing in Enhanced Due Diligence (EDD) requirements in {jurisdiction}.

# Document Context
Circular Number: {circular_number}
Effective Date: {effective_date}
Issuing Authority: {issuing_authority}
Regulator: {regulator}

# Text to Analyze
{chunk_text}

# Task
Extract ALL Enhanced Due Diligence (EDD) trigger conditions mentioned in this text.

For each EDD trigger, provide complete structured data:

{{
  "edd_triggers": [
    {{
      "trigger_category": "pep | high_risk_jurisdiction | high_risk_customer | complex_structure | unusual_activity",
      "pep_tier": "domestic_pep | foreign_pep | international_org | family_member | close_associate | null",
      "relationship_types": ["customer", "beneficial_owner", "authorized_signer"],
      "required_approvals": ["senior_management", "compliance_officer"],
      "enhanced_measures": [
        "source_of_wealth_verification",
        "source_of_funds_verification",
        "ongoing_monitoring_enhanced",
        "periodic_review_<X>_months"
      ],
      "source_text": "exact quote",
      "page_reference": <int or null>,
      "confidence": <0.0 to 1.0>
    }}
  ]
}}

# Extraction Guidelines
1. Identify the specific trigger category (PEP, high-risk jurisdiction, etc.)
2. For PEP triggers, specify the tier/classification
3. Capture ALL required enhanced measures as separate list items
4. Include approval requirements (e.g., senior management sign-off)
5. Mark confidence < 0.7 if EDD requirements are vague
6. Return empty array if NO EDD triggers found

Output ONLY valid JSON."""


SANCTIONS_EXTRACTION_PROMPT = """You are an expert AML compliance analyst specializing in sanctions screening requirements in {jurisdiction}.

# Document Context
Circular Number: {circular_number}
Effective Date: {effective_date}
Issuing Authority: {issuing_authority}
Regulator: {regulator}

# Text to Analyze
{chunk_text}

# Task
Extract ALL sanctions screening and compliance requirements.

{{
  "sanctions_rules": [
    {{
      "sanctions_list": "UNSC | OFAC | EU | MAS | HKM | national_list",
      "screening_frequency": "real_time | daily | weekly | onboarding_only",
      "match_threshold": <0.0 to 1.0 or null>,
      "escalation_procedures": ["procedure", "steps"],
      "applies_to": ["customers", "transactions", "beneficial_owners"],
      "source_text": "exact quote",
      "page_reference": <int or null>,
      "confidence": <0.0 to 1.0>
    }}
  ]
}}

# Extraction Guidelines
1. Identify specific sanctions lists referenced (UN, OFAC, etc.)
2. Capture screening frequency requirements
3. Note any fuzzy matching thresholds if mentioned
4. Include escalation procedures for matches
5. Return empty array if NO sanctions rules found

Output ONLY valid JSON."""


RECORD_KEEPING_EXTRACTION_PROMPT = """You are an expert AML compliance analyst specializing in record-keeping and retention requirements in {jurisdiction}.

# Document Context
Circular Number: {circular_number}
Effective Date: {effective_date}
Issuing Authority: {issuing_authority}
Regulator: {regulator}

# Text to Analyze
{chunk_text}

# Task
Extract ALL record-keeping and retention requirements.

{{
  "record_keeping_rules": [
    {{
      "record_type": "transaction_records | customer_identification | correspondence | sar_documentation",
      "retention_period_years": <integer>,
      "storage_requirements": ["secure", "retrievable", "audit_trail"],
      "applies_to": ["entity", "types"],
      "source_text": "exact quote",
      "page_reference": <int or null>,
      "confidence": <0.0 to 1.0>
    }}
  ]
}}

# Extraction Guidelines
1. Extract retention period in years
2. Note any specific storage requirements (e.g., secure, electronic, retrievable)
3. Identify which records the retention applies to
4. Return empty array if NO record-keeping rules found

Output ONLY valid JSON."""


# Prompt template mapping
PROMPT_TEMPLATES = {
    "threshold": THRESHOLD_EXTRACTION_PROMPT,
    "deadline": DEADLINE_EXTRACTION_PROMPT,
    "edd_trigger": EDD_TRIGGER_EXTRACTION_PROMPT,
    "sanctions": SANCTIONS_EXTRACTION_PROMPT,
    "record_keeping": RECORD_KEEPING_EXTRACTION_PROMPT,
}


def build_extraction_prompt(
    rule_type: str,
    jurisdiction: str,
    circular_number: str,
    effective_date: str,
    issuing_authority: str,
    regulator: str,
    chunk_text: str,
    default_currency: str = "SGD"
) -> str:
    """
    Build extraction prompt for a specific rule type.

    Args:
        rule_type: Type of rule to extract
        jurisdiction: Jurisdiction code
        circular_number: Regulatory circular number
        effective_date: Effective date of regulation
        issuing_authority: Issuing authority name
        regulator: Regulator abbreviation
        chunk_text: Document text to analyze
        default_currency: Default currency if not stated

    Returns:
        Formatted prompt string

    Raises:
        ValueError: If rule_type not recognized
    """
    template = PROMPT_TEMPLATES.get(rule_type)
    if not template:
        raise ValueError(f"Unknown rule_type: {rule_type}")

    return template.format(
        jurisdiction=jurisdiction,
        circular_number=circular_number,
        effective_date=effective_date or "Not specified",
        issuing_authority=issuing_authority,
        regulator=regulator,
        chunk_text=chunk_text,
        default_currency=default_currency
    )


# Result key mapping (JSON response key for each rule type)
RESULT_KEYS = {
    "threshold": "thresholds",
    "deadline": "deadlines",
    "edd_trigger": "edd_triggers",
    "sanctions": "sanctions_rules",
    "record_keeping": "record_keeping_rules",
}
