# Phase 1 Data Model: Deterministic Routing

This document names the in-memory entities the router operates on and pins
their derivation rules. The *persisted* artifact shape is owned by the frozen
JSON Schema at `contracts/stage1_vendor_identity/v1.0.0/routing_decision.schema.json`
and is not redefined here. Everything below is the **internal** data the
router's pure functions pass around, plus the mapping between that data and
the persisted contract.

## Entities

### `InputArtifact` (read-only)

The loaded, schema-validated `edge_extraction_output.json` dict. After a
successful load via `input_loader.py`:

| Field | Type | Source | Used by |
|-------|------|--------|---------|
| `contract_set_version` | `str` | schema required | Asserted `== "1.0.0"`; drift → `VersionDriftError` (Decision 2). |
| `document_id` | `str` | schema required | Copied verbatim to output. |
| `processed_at` (input's) | `str` (ISO-8601) | schema required | Ignored — output uses the router's own timestamp. |
| `status` | `"success" \| "partial" \| "failure"` | schema required | Drives `rules.evaluate()` via upstream-failure / partial paths (Decision 11). |
| `vendor_candidate` | `VendorCandidate` | schema required | Primary input to checks, scores, and rules. |
| `invoice_header_fields` | `object` | schema required | **Ignored** — routing is vendor-identity-only (spec constitution gate). |
| `extraction_notes`, `warnings` | `list[str]` | schema required | Informational; surfaced nowhere by default (routing's decision is based on structural shape, not narrative — spec edge case at line 117). |

The router MUST NOT mutate this dict. It is treated as read-only in memory.

### `VendorCandidate` (sub-entity of `InputArtifact`)

Directly maps to the schema's `vendor_candidate` sub-object:

| Field | Type | Shape |
|-------|------|-------|
| `company_name` | `CompanyNameField` | `{value, present, inferred, confidence, evidence}` |
| `address` | `AddressField` | six sub-fields: `street_1, street_2, city, state, postal_code, country`, each `{value, confidence, evidence}` |
| `tax_ids` | `TaxIdsField` | four sub-fields: `ein, state_tax_id, vat_id, other_tax_id`, each `{value, confidence, evidence}` |
| `website` | `ValueField` | `{value, confidence, evidence}` |
| `phone` | `ValueField` | `{value, confidence, evidence}` |
| `email` | `ValueField` | `{value, confidence, evidence}` |

### `ValueField` (structural predicate `is_grounded`)

A `ValueField` (`value`, `confidence`, `evidence`) is **grounded** iff:

```python
value is not None AND len(evidence) >= 1
```

`confidence` has no role in grounding (FR-018, clarification Q1). This predicate
is the single definition used by every check and every score.

The `company_name` field has the additional predicate `is_explicit`:

```python
company_name.present == True AND company_name.inferred == False AND len(company_name.evidence) >= 1
```

### `ChecksBlock` (derived)

The six booleans the router publishes. Each is a pure function of the input:

| Key | Source rule | FR reference |
|-----|-------------|--------------|
| `company_name_present` | Direct copy of `vendor_candidate.company_name.present`. No re-derivation. | FR-009 |
| `company_name_inferred` | Direct copy of `vendor_candidate.company_name.inferred`. No re-derivation. | FR-009 |
| `address_has_minimum_components` | `is_grounded(city) AND is_grounded(state) AND is_grounded(postal_code)` — all three required. Street-only or country-only or any 2-of-3 subset → `false`. | FR-010 |
| `at_least_one_tax_id_present` | `any(is_grounded(f) for f in [ein, state_tax_id, vat_id, other_tax_id])`. | FR-011 |
| `website_or_email_present` | `is_grounded(website) OR is_grounded(email)`. Phone is NOT counted here. | FR-012 |
| `post_extraction_spam_gate_passed` | `false` iff **all** of: `company_name.value is None`, every address-component value is `None`, every tax-ID value is `None`, `website.value is None`, `phone.value is None`, `email.value is None`. Otherwise `true`. | FR-013 |

Values are plain Python `bool`. No `None`, no string truthy/falsy.

### `ScoresBlock` (derived)

Five numeric roll-ups in `[0.0, 1.0]`. Formulas pinned by `policy_version`
(clarification Q2, FR-017):

| Key | Formula | Notes |
|-----|---------|-------|
| `company_name_score` | `1.0` if `company_name.is_explicit`, else `0.0`. | Binary: explicit-and-evidenced or not. |
| `address_score` | `count_grounded({street_1, city, state, postal_code, country}) / 5`. | `street_2` excluded (research Decision 5). |
| `tax_id_score` | `count_grounded({ein, state_tax_id, vat_id, other_tax_id}) / 4`. | Four fixed slots. |
| `contact_score` | `count_grounded({website, phone, email}) / 3`. | Three fixed slots. |
| `overall_vendor_identity_score` | Arithmetic mean of the four above (equal weight). | Sum-of-four / 4. |

Each score is a Python `float`. No rounding; values are exact rationals with
small denominators (research Decision 7).

### `SecondaryIdentifierFloor` (derived, internal only)

Not published in the artifact, but used by the secondary-identifier-floor
rule (FR-014). Four independent slots:

1. `checks.address_has_minimum_components`
2. `checks.at_least_one_tax_id_present`
3. `checks.website_or_email_present`
4. `is_grounded(vendor_candidate.phone)`

```python
floor_met = sum(1 for slot in [slot_1, slot_2, slot_3, slot_4] if slot) >= 2
```

Phone counts as an independent slot because the schema's `checks` block has no
`phone_present` boolean (research Decision 6).

### `RuleResult` (derived, internal only)

Each rule evaluation produces:

```python
class RuleResult:
    rule_id: Literal[
        "missing_name",
        "spam_gate",
        "secondary_identifier_floor",
        "upstream_failure",
    ]
    fired: bool              # rule applied to this document
    forces_review: bool      # rule, when fired, forces edge_review_required
    canonical_reason: str    # e.g. "company_name_inferred"
    priority: int            # 1..4 per FR-015; lower = higher priority
```

The rule table:

| `rule_id` | Fired when | Forces review? | `canonical_reason` | Priority |
|-----------|------------|----------------|--------------------|----------|
| `missing_name` | `company_name.inferred == true` OR `company_name.present == false` | **Yes** | `"company_name_inferred"` | 1 |
| `spam_gate` | `checks.post_extraction_spam_gate_passed == false` | **Yes** | `"post_extraction_spam_gate_failed"` | 2 |
| `secondary_identifier_floor` | Floor not met (< 2 slots true) | **Yes** | `"secondary_identifiers_insufficient"` | 3 |
| `upstream_failure` | Input `status == "failure"` | **Yes** | `"upstream_extraction_failed"` | 4 |

### `RoutingDecision` (assembled, matches frozen schema)

Direct mapping to `routing_decision.schema.json`. Assembly order (matches
`required` in the schema):

```python
{
    "contract_set_version": "1.0.0",
    "pipeline_version": build_pipeline_version(),
    "policy_version": POLICY_VERSION,
    "document_id": input_artifact["document_id"],
    "processed_at": now_utc_rfc3339(),
    "status": derived_output_status,           # Decision 11
    "decision": derived_decision,               # "edge_accept" or "edge_review_required"
    "consensus_summary": {
        "mode": "single_voter_baseline",
        "agreement_level": "not_applicable",
    },
    "scores": {...},                            # ScoresBlock
    "checks": {...},                            # ChecksBlock
    "review_status": {
        "manual_review_required": bool,
        "review_reason": str | None,
    },
    "reasons": [str, ...],                      # ReasonsArray
}
```

### `ReasonsArray` (derived, pinned ordering)

Canonical ordering (clarification Q3, FR-015):

1. **Forcing rules**, in priority order (1 → 4), for each fired rule:
   its canonical reason string.
2. **Affirmatives** (only when `decision == "edge_accept"`), in this fixed
   order: `"company_name_explicit"`, `"spam_gate_passed"`,
   `"secondary_identifier_floor_met"`, `"upstream_extraction_ok"`.
3. **Informational entries**, in this fixed order:
   `"upstream_status_partial"` (when input `status == "partial"`),
   `"contract_violation_detected"` (when FR-024 triggers).

The array is emitted with no duplicates and in the order above. Two runs of
the same input produce the same array byte-for-byte.

### `ReviewStatus` (derived)

```python
if decision == "edge_accept":
    review_status = {"manual_review_required": False, "review_reason": None}
else:  # edge_review_required
    review_status = {
        "manual_review_required": True,
        "review_reason": highest_priority_fired_rule.canonical_reason,
    }
```

FR-007 enforces that `decision` and `review_status` cannot disagree; the
assembly code constructs `review_status` from `decision` + firing rules in one
step, making disagreement impossible by construction.

## State transitions

The router is stateless — no persistent state beyond the read input and the
written output. Within a single invocation:

```text
load → validate input → compute checks → compute scores → evaluate rules →
  derive decision + review_status + status → assemble reasons → assemble dict →
  validate against output schema → atomic write → print stdout JSON summary
```

Each step is a pure function (except for the first and last). A failure at any
step before the atomic write results in no artifact and a non-zero exit code
(contracts/cli-contract.md).

## Validation rules (collected)

- **Input schema**: Every input must validate against
  `edge_extraction_output.schema.json` before any rule fires. Failure →
  `MalformedInputError` → exit code `2`, no artifact.
- **Input contract-set version**: Must be exactly `"1.0.0"`. Drift →
  `VersionDriftError` → exit code `2`, no artifact.
- **Output schema**: Every assembled dict must validate against
  `routing_decision.schema.json` before the atomic write. Failure →
  `ContractAssertionError` → exit code `3`, no artifact (this would be an
  internal bug — the router built something its own schema rejects).
- **FR-024 forbidden combos**: If the input violates extractor FR-013
  (`company_name.present == true AND company_name.inferred == true`, or
  `present == false AND inferred == false`), the router does not crash; it
  sets `status = "partial"`, `decision = "edge_review_required"`, adds
  `"contract_violation_detected"` to `reasons`, and proceeds with the
  defensive path.
- **FR-007 decision / review_status consistency**: Enforced by construction
  (one assembly step produces both from the same inputs).
- **FR-021 byte-identical determinism**: Enforced by explicit assembly order,
  fixed JSON dump settings (research Decision 7), and pure functions with no
  dict iteration dependencies.
