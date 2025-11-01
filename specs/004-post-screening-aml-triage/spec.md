# Feature Specification: Post-Screening AML Triage Layer

**Feature Branch**: `feature/004-post-screening-aml-triage`  
**Created**: 2025-11-01  
**Status**: Draft  
**Input**: User description: "Feature name: 004-post-screening-AML-triage

Problem:
After screening, analysts receive PASS/SUS/FAIL but lose time deciding next steps. We need a consistent triage layer that reads the reasons (rule codes, corridor, behavioural patterns) and proposes compliant, auditable actions.

Users & value:
• AML analysts (L1/L2): faster alert triage; standardised actions; fewer misses.
• Relationship Managers / KYC Ops: clear, templated communications and document requests.
• Compliance / MLRO: auditable plans aligned to policy; approvals where required.
• Engineering: deterministic, contract-first interface (JSON-in / JSON-out) around the LLM.

Scope (this feature):
• Input: Screening Result JSON (decision + reasons + evidence).
• Output: Plan JSON (whitelisted actions, comms template IDs, rationales, confidence).
• Policy guardrails: schema validation; allowed actions only; approval gating.
• Template Library: versioned, scenario/action templates the LLM must consult.
• Contract Registry: easy-to-evolve input contract (versioned schema + alias map).
• Feedback loop: reviewers tag plan quality (e.g., good_sus/bad_sus) to improve future plans.

Out of scope:
• Building the upstream screening engine.
• Executing real core-banking actions (adapters are stubs for the demo).
• Free-text customer messaging by the LLM (use comms templates only).

Success metrics:
• ≥ 80% reviewer plan acceptance.
• ≥ 30% reduction in time-to-triage vs baseline.
• 0 production breaches of “disallowed actions”.

Constraints:
• PII minimised in prompts; full audit logs; idempotent tool calls.
• Must run offline on mocks during the hackathon.
• All code under backend/src/AML_triage; mountable into the team’s backend."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyst triages alert (Priority: P1)

An AML L1 analyst receives a SUS screening result and requests an automated triage plan so they can decide next actions without manually parsing rule codes.

**Why this priority**: Directly addresses the primary latency problem and unlocks the value proposition for analysts.

**Independent Test**: Feed representative SUS JSON into the service and verify the returned plan is actionable, policy-compliant, and auditable without other stories implemented.

**Acceptance Scenarios**:

1. **Given** a SUS screening result with multiple rule codes and evidence artefacts, **When** the analyst submits it to the triage API, **Then** the system returns a plan JSON containing prioritized, whitelisted actions and corresponding rationales.
2. **Given** a PASS result with no follow-up required, **When** the analyst submits it, **Then** the system returns a minimal plan confirming closure and logging the decision without suggesting disallowed actions.

---

### User Story 2 - Compliance review gates approvals (Priority: P2)

A compliance reviewer or MLRO evaluates proposed high-risk actions and records approval outcomes inside the triage plan for downstream auditability.

**Why this priority**: Ensures regulatory obligations are met before execution and prevents disallowed actions, enabling production readiness.

**Independent Test**: Simulate a plan containing approval-required actions and confirm the reviewer workflow captures gating decisions and audit logs without depending on RM communications.

**Acceptance Scenarios**:

1. **Given** a triage plan that flags an action requiring compliance approval, **When** a reviewer records an approval decision, **Then** the plan state updates with reviewer identity, timestamp, and final action status while preserving an immutable audit trail.

---

### User Story 3 - Relationship manager communication (Priority: P3)

A Relationship Manager needs to request documentation from a customer based on the triage plan and pulls the correct template message with pre-filled contextual fields.

**Why this priority**: Provides clear downstream communication, reducing manual drafting effort and inconsistencies.

**Independent Test**: From a generated plan, retrieve the referenced communication template and verify the populated message matches the scenario, using only approved template IDs.

**Acceptance Scenarios**:

1. **Given** a plan referencing a document request template, **When** the RM retrieves the template via the plan output, **Then** the system returns the correct versioned template with placeholders populated from the screening evidence and policy-compliant messaging.

---

### Edge Cases

- Unsupported or unrecognized rule codes appear in the screening result; the system must degrade gracefully with a fallback action and flag for policy review.
- Evidence objects are missing or redacted; triage must note insufficient evidence and request clarifications without breaching disallowed actions.
- Conflicting recommendations emerge from different rules; the plan must reconcile them into a single ordered action set with rationales for chosen precedence.
- Repeated submissions of the same screening result occur; the service must detect duplicates and return the existing plan to maintain idempotency.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The triage API MUST accept Screening Result JSON payloads that conform to the versioned schema defined in the contract registry, rejecting invalid payloads with actionable error messages.
- **FR-002**: The system MUST validate the decision, reasons, and evidence fields against the schema and normalize aliases via the contract registry before plan generation.
- **FR-003**: The triage engine MUST map rule codes, corridors, and behavioral patterns to a ranked list of whitelisted actions using the template library and policy guardrails.
- **FR-004**: The generated plan JSON MUST include action identifiers, rationales, confidence scores, required approvals, and linked communication template IDs drawn from the approved library.
- **FR-005**: The system MUST enforce policy guardrails by blocking any action not present in the whitelist and logging the refusal with context.
- **FR-006**: The service MUST support approval gating workflows whereby reviewer decisions update plan status while preserving immutable audit logs.
- **FR-007**: The contract registry MUST track schema versions and alias mappings, enabling deterministic negotiation between upstream screening outputs and the triage service.
- **FR-008**: The template library MUST provide versioned, scenario-specific templates accessible by template ID, with metadata for channel, language, and compliance notes.
- **FR-009**: The triage service MUST operate offline on mock data by loading local models, templates, and guardrails without external network calls.
- **FR-010**: The feedback loop MUST allow reviewers to tag plan quality outcomes using the allowed labels (`good_pass`, `bad_pass`, `good_sus`, `bad_sus`, `good_fail`, `bad_fail`) and optional `action_fit` ∈ [0,1], persisting them for future evaluation of triage performance.
- **FR-011**: The system MUST maintain full audit logs for inputs, generated plans, approvals, and feedback events, ensuring traceability for compliance review.
- **FR-012**: The plan response MUST include analyst-ready summary statistics: counts by action type, identification of actions pending human approval, corridor risk classification, and aggregate confidence averages.
- **FR-013**: The policy guardrails MUST codify approval rules whereby `PLACE_SOFT_HOLD` and `FILE_STR_DRAFT` require human approval, while other whitelisted actions may be auto-suggested.
- **FR-014**: The triage policy MUST treat corridors with FATF high-risk classification and transaction amounts ≥ 10k (base currency) as escalation scenarios, flagging them for reviewer attention within the plan output.

### Key Entities *(include if feature involves data)*

- **ScreeningResult**: Represents PASS/SUS/FAIL outcomes with associated rule codes, corridor metadata, behavioral patterns, and evidence artefacts; versioned via the contract registry.
- **ActionPlan**: Encapsulates the ordered list of triage actions, rationales, confidence, required approvals, communication templates, and summary statistics.
- **PlanAction**: Individual recommended action entries including action ID, description, prerequisites, approval status, and whitelisted metadata.
- **TemplateReference**: Links plan actions to versioned communication templates with localization data and placeholders for contextual fields.
- **PolicyGuardrail**: Defines allowed actions, disallowed operations, approval thresholds, and auditing requirements enforced during plan generation.
- **FeedbackRecord**: Captures reviewer tags (e.g., `good_sus`, `bad_sus`), analyst comments, and plan identifiers for continuous improvement loops.

### Assumptions

- Analysts and reviewers authenticate through an existing identity layer; this feature consumes the authenticated user context without managing identities.
- The whitelist of actions and templates will be provided by Compliance before go-live and updated via configuration files within the repository.
- Time-to-triage baselines are already measured externally; this feature will emit timestamps to support comparative reporting but will not calculate the baseline itself.
- High-risk jurisdictions default to the FATF high-risk (mock) list, and PASS/SUS/FAIL semantics follow the agreed mapping (FAIL = hard stop, SUS = open case + review, PASS = close barring policy exceptions).
- Plan data and feedback labels persist locally in SQLite and JSON logs for the duration of the hackathon demo environment.
- Communication outputs remain template-only, with RM briefs styled as professional internal memos and customer document requests neutral in tone.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ≥ 80% of reviewer assessments (good_sus/bad_sus tags) accept generated plans without manual overrides during pilot.
- **SC-002**: Analysts complete post-screening triage in ≤ 70% of the baseline time for comparable alert volumes, measured by elapsed time between plan request and resolution log.
- **SC-003**: 0 instances of disallowed actions appearing in production plans over the evaluated period, verified via audit log scans.
- **SC-004**: 100% of plan requests, approvals, and feedback events produce immutable audit records accessible for compliance review within 24 hours.
- **SC-005**: Offline mock execution handles at least 50 representative screening scenarios per corridor without requiring external network connectivity.
