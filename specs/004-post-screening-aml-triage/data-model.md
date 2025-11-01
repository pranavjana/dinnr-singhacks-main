# Data Model — Post-Screening AML Triage Layer

## ScreeningResult
- **Fields**
  - `schema_version` (str): contract version (default `v1`); must match registry.
  - `decision` (enum: `PASS`, `SUS`, `FAIL`): mapped semantics (PASS=close barring exceptions, SUS=open case, FAIL=hard stop).
  - `rule_codes` (list[str]): triggered rules; normalized via alias map.
  - `corridor` (object): `origin_country`, `destination_country`, `channel`, `currency`.
  - `amount` (number): transaction amount in base currency; used for high-risk threshold (≥10k triggers escalation).
  - `behavioural_patterns` (list[str]): pattern identifiers.
  - `evidence` (list[object]): structured references to documents/events with `type`, `id_hash`, `uri`, `summary`.
  - `metadata` (object, optional): upstream identifiers (hashed) and timestamps.
- **Validation Rules**
  - Reject unknown fields when `STRICT_FIELDS=true`.
  - Require `decision`, `rule_codes`, and `corridor`.
  - Apply alias normalization before downstream processing.
- **Relationships**
  - Serves as input for `TriageState.ingestion_result`.

## ActionCatalogueEntry
- **Fields**
  - `action_id` (str): canonical identifier.
  - `description` (str).
  - `requires_approval` (bool): `true` for `PLACE_SOFT_HOLD`, `FILE_STR_DRAFT`.
  - `allowed_if` (list[condition]): corridor/rule predicates.
  - `tool` (str) and `params` (dict): adapter invocation details.
  - `compliance_notes` (str) and `risk_tier` (enum).
- **Validation Rules**
  - Must reference an existing template in `templates/index.json`.
  - Conditions must refer to schema-sanctioned fields.
- **Relationships**
  - Referenced by `PlanAction.action_id` and LangGraph policy nodes.

## TemplateDefinition
- **Fields**
  - `template_id` (str), `action_id` (str).
  - `version` (semver), `locale`, `channel`.
  - `purpose`, `when_to_use`, `preconditions`, `playbook_steps`.
  - `required_fields` (list[str]), `compliance_notes`.
  - `fewshot_examples` (list[short-text]).
- **Validation Rules**
  - `action_id` must exist in catalogue.
  - `fewshot_examples` length capped (≤3) to satisfy token constraints.

## Plan
- **Fields**
  - `plan_id` (uuid).
  - `input_hash` (str): sha256 of normalized ScreeningResult.
  - `schema_version` (str): plan schema version.
  - `summary` (object): counts by action type, approvals pending, corridor risk class, confidence aggregates.
  - `recommended_actions` (list[`PlanAction`]).
  - `communications` (list[`CommInstruction`]).
  - `rationales` (list[str]).
  - `confidence` (float 0–1).
  - `approvals_required` (list[`ApprovalRequest`]).
  - `audit` (object): timestamps, agent iteration count, `templates_used`, `aliases_used`.
- **Validation Rules**
  - `recommended_actions` references must match whitelist.
  - Confidence ∈ [0,1]; approvals required present when `requires_approval` true.
- **Relationships**
  - Stored in SQLite `plans` table; joined with feedback records.

## PlanAction
- **Fields**
  - `action_id` (str).
  - `status` (enum: `SUGGESTED`, `APPROVED`, `REJECTED`, `EXECUTED`).
  - `priority` (int).
  - `rationale` (str).
  - `confidence` (float).
  - `requires_approval` (bool).
  - `template_ids` (list[str]).
- **Validation Rules**
  - `priority` positive.
  - `requires_approval` must mirror catalogue metadata.
- **State Transitions**
  - `SUGGESTED` → `APPROVED` when reviewer ok; `APPROVED` → `EXECUTED` via adapter stub; `SUGGESTED` → `REJECTED` on reviewer decline.

## CommInstruction
- **Fields**
  - `template_id` (str).
  - `audience` (enum: `RM`, `CUSTOMER`).
  - `tone` (enum: `PROFESSIONAL_INTERNAL`, `NEUTRAL_EXTERNAL`).
  - `placeholders` (dict[str,str]).
  - `delivery_channel` (enum: `EMAIL`, `PORTAL_TASK`).
- **Validation Rules**
  - `tone` derived from default rules (RM professional, customer neutral).
  - Placeholders must be subset of template required fields.

## FeedbackRecord
- **Fields**
  - `plan_id` (uuid).
  - `label` (enum: `good_pass`, `bad_pass`, `good_sus`, `bad_sus`, `good_fail`, `bad_fail`).
  - `action_fit` (float 0–1, optional).
  - `reviewer_id_hash` (str).
  - `notes` (str, optional, masked for PII).
  - `created_at` (datetime).
- **Validation Rules**
  - Unique `(plan_id, reviewer_id_hash)` to ensure idempotency.
  - `action_fit` required when label starts with `bad_`.
- **Relationships**
  - Retrieved for few-shot context keyed by `(rule_code set, corridor risk tier, decision)`.

## AuditLogEntry
- **Fields**
  - `timestamp` (datetime UTC).
  - `event` (enum: `INGEST`, `VALIDATION_PASS`, `LLM_REQUEST`, `LLM_RESPONSE`, `PLAN_EMITTED`, `APPROVAL_UPDATED`, `FEEDBACK_RECORDED`).
  - `trace_id` (uuid).
  - `user_hash` (str or null).
  - `details` (json blob with masked identifiers).
- **Validation Rules**
  - `details` must omit raw PII; hashed fields appended with `_hash`.
- **Relationships**
  - Written alongside SQLite transactions for compliance trail; exportable to downstream systems.
