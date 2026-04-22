# Phase 0 Research: 009-final-payload

All open questions from `spec.md` resolved. The five clarifications already integrated into
the spec (Clarifications Session 2026-04-21) are not repeated here — they are authoritative.
This document captures the ten plan-level decisions needed before Phase 1 design.

## Decision 1 — Deterministic JSON write format

**Decision**: Write `final_structured_payload.json` with `json.dumps(obj, ensure_ascii=False, indent=2, separators=(",", ": "), sort_keys=False)` plus a trailing `"\n"`, UTF-8. Top-level and nested keys are emitted in a **fixed insertion order** that matches the schema's declared property order (not `sort_keys=True`). A single `FINAL_KEY_ORDER` constant in `assembler/write.py` pins the top-level order; sub-dicts are assembled in Python 3.7+ insertion order.

**Rationale**: `sort_keys=True` would produce alphabetical order, which differs from the human-readable schema order (`contract_set_version`, `pipeline_version`, `document_id`, …) already used by the validator's report output and the preprocessing slice. Fixed insertion order is equally deterministic and easier to diff against the schema. The trailing newline matches the preprocessing slice's existing convention and keeps POSIX tooling happy.

**Alternatives considered**: (a) `sort_keys=True` — deterministic but breaks the readable schema-order convention. (b) Raw `json.dumps` default separators — deterministic but introduces trailing spaces on some platforms depending on separator behavior. (c) Custom serializer — overkill for this slice.

## Decision 2 — `processed_at` format

**Decision**: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` — ISO-8601, UTC, second-precision, `Z` suffix (no `+00:00`).

**Rationale**: The schema requires `format: date-time`. Fixed-width `Z`-suffix format is compact, trivially diffable, and matches the existing preprocessing slice. Sub-second precision adds drift without analytic value for an artifact-to-artifact assembler that runs under 200 ms.

**Alternatives considered**: (a) `.isoformat()` — includes microseconds and a `+00:00` offset; both are valid date-time but less uniform. (b) Millisecond precision — not needed at this latency. (c) Overrideable-from-env "frozen time" for testing — test suites should inject via dependency injection on the `Invocation` rather than env vars (see module-api contract).

## Decision 3 — `pipeline_version` format

**Decision**: Fixed string `"009-final-payload@0.1.0"`, constructed as `f"{SLICE_PREFIX}@{SEMVER}"` where `SLICE_PREFIX = "009-final-payload"` and `SEMVER = "0.1.0"` live in `assembler/version.py`. `build_pipeline_version(semver: str = SEMVER) -> str` returns the full string; callers can override `semver` only in tests.

**Rationale**: Pinned by Clarification Q2/FR-007. Any change to the `overall_vendor_confidence` formula or the `secondary_identifiers_found` ordering bumps `SEMVER`. The `SLICE_PREFIX` never changes for this feature.

**Alternatives considered**: (a) Include PaddleOCR version + weights hash like the preprocessing slice — not applicable; the assembler calls no OCR. (b) Include the assembler module's source hash — would break byte-identical reruns across commits that don't change behavior. (c) Free-form — rejected by the clarification.

## Decision 4 — Schema validation reuse

**Decision**: Import `load_and_validate` (or equivalent) from `ledgerlinc_ocr.validator.artifact` for both inputs' validation and for the output's validation pre-write. Do not duplicate the `jsonschema` wiring. Schema files are resolved relative to `contracts/stage1_vendor_identity/v1.0.0/` using the same helper the validator uses.

**Rationale**: The validator already owns schema loading, Draft 2020-12 setup, and artifact-type-to-schema resolution. Reusing it keeps the contract surface single-sourced — a future contract-set bump touches one loader, not two.

**Alternatives considered**: (a) Re-implement a local validator — duplicates risk. (b) Call the validator CLI as a subprocess — overkill and slow. (c) Skip input validation and trust the upstream slices — violates FR-003 which explicitly requires per-input schema validation.

## Decision 5 — Exit code table

**Decision**: Mirror the existing preprocessing slice's exit codes:
- `0` = OK (payload written, schema-valid).
- `1` = Unexpected (uncaught exception — should never happen in normal operation).
- `2` = Input rejected (any of: missing input, unreadable input, schema-invalid input, contract-set drift, document_id mismatch, routing contradiction per FR-016).
- `3` = Internal error (assembled payload failed its own schema validation — indicates a code/contract mismatch, should never happen).

Every non-zero exit writes a single JSON line to stderr: `{"status": "error", "kind": "<kind>", "message": "<human-readable>"}` where `kind` is one of `missing_input`, `unreadable_input`, `schema_invalid_input`, `contract_drift`, `document_id_mismatch`, `routing_contradiction`, `output_schema_invalid`, `unexpected`.

**Rationale**: The existing preprocessing slice (`src/ledgerlinc_ocr/preprocessing/errors.py`) uses exactly this 4-way split. Matching it keeps the pipeline CLI surface uniform and lets downstream orchestration treat "exit 2" as "bad input, diagnose the artifacts" across all stages.

**Alternatives considered**: (a) A unique code per `kind` — leaks internal taxonomy into shell scripts. (b) Collapse `2` and `3` — obscures the distinction between "the input is bad" (recoverable by fixing upstream) and "the assembler is bad" (requires a code fix).

## Decision 6 — `overall_vendor_confidence` rounding

**Decision**: After computing the pinned formula `clip(0.5 * company_name.confidence + 0.5 * mean(secondary confidences, default 0.0), 0.0, 1.0)`, round to **4 decimal places** via `round(value, 4)` before writing.

**Rationale**: FR-022 requires byte-identical output across runs. Raw Python floats can differ in the trailing bits across platforms or interpreter versions; 4 decimals is more than enough resolution for a `[0, 1]` signal (SC-001 does not require sub-percent precision) and eliminates drift. JSON serializes `round(0.12345, 4)` as `0.1234` cleanly.

**Alternatives considered**: (a) No rounding — risks cross-platform drift. (b) 6 or more decimals — no analytic value, larger drift surface. (c) `decimal.Decimal` — overkill; the inputs are JSON-parsed floats to begin with.

## Decision 7 — Evidence-stripping shape (FIELDS_TO_FLATTEN table)

**Decision**: A single declarative table in `assembler/flatten.py` drives every flatten step. Shape:

```python
# Each entry: (extractor_path, final_payload_path, kind)
# kind ∈ {"value_confidence", "company_name"}
FIELDS_TO_FLATTEN = [
    (["vendor_candidate", "company_name"], ["vendor_candidate", "company_name"], "company_name"),
    (["vendor_candidate", "address", "street_1"], ["vendor_candidate", "address", "street_1"], "value_confidence"),
    # ... street_2, city, state, postal_code, country
    (["vendor_candidate", "tax_ids", "ein"], ["vendor_candidate", "tax_ids", "ein"], "value_confidence"),
    # ... state_tax_id, vat_id, other_tax_id
    (["vendor_candidate", "website"], ["vendor_candidate", "website"], "value_confidence"),
    (["vendor_candidate", "phone"], ["vendor_candidate", "phone"], "value_confidence"),
    (["vendor_candidate", "email"], ["vendor_candidate", "email"], "value_confidence"),
]
```

`value_confidence` copies `{value, confidence}`. `company_name` copies `{value, present, inferred, confidence}`. Neither ever emits `evidence`. The table is the single source of truth; no per-field if-branches elsewhere.

**Rationale**: The schema has many scalar fields. A declarative table is auditable (grep for the table to see every flattened field), makes FR-014 ("no evidence key anywhere in output at any nesting depth") a table property rather than a scattered invariant, and keeps tests trivial (one parameterized test over the table).

**Alternatives considered**: (a) Walk the schema at runtime — flexible but opaque; test failures would be confusing. (b) Per-field explicit functions — verbose and error-prone; easy to forget to strip evidence on one field. (c) Pydantic models with exclude_evidence=True — pulls in validation machinery that duplicates Decision 4's schema validator.

## Decision 8 — `secondary_identifiers_found` derivation independence

**Decision**: The assembler re-derives `secondary_identifiers_found` **locally from the extractor's output** (not from `routing_decision.json:checks`). Address is included iff `extractor.vendor_candidate.address.{city,state,postal_code}` each have `value != null` AND `len(evidence) > 0`. Each tax-ID is included iff `extractor.vendor_candidate.tax_ids.<slot>.value != null` AND `len(evidence) > 0`. Website/phone/email each iff `value != null` AND `len(evidence) > 0`. Output order: exactly the schema enum's declared order (Clarification Q3 / FR-020).

**Rationale**: The spec pins the rule to routing's `address_has_minimum_components` *definition*, not to routing's *value*. Re-deriving locally (a) keeps `quality_summary` independent of whether routing's contract later adds/removes a `checks` key, (b) lets the assembler still emit a correct `quality_summary` even when the FR-016 contradiction check fires — no, actually the contradiction check fires BEFORE assembly, so that's moot, but keeping independence is still cleaner, (c) matches FR-020's explicit definition of each identifier's inclusion rule.

**Alternatives considered**: (a) Copy `routing.checks.address_has_minimum_components` directly — leaks routing's internal bookkeeping into the final payload's derivation chain. (b) Derive partly from routing and partly from the extractor — inconsistent.

## Decision 9 — FR-016 routing-contradiction detection

**Decision**: A single function `check_routing_internal_consistency(routing: dict) -> None` raises `RoutingContradictionError` (exit 2) iff any of:
- `routing.decision == "edge_accept"` AND `routing.review_status.manual_review_required == true`.
- `routing.decision == "edge_accept"` AND `routing.review_status.review_reason != null`.
- `routing.decision == "edge_review_required"` AND `routing.review_status.manual_review_required == false`.
- `routing.decision == "edge_review_required"` AND `routing.review_status.review_reason == null`.

The error message names both `decision` and the conflicting `review_status` fields. This check runs AFTER per-input schema validation and AFTER the contract-set-version / document_id checks, so failures are reported in a stable order.

**Rationale**: Clarification Q1 / FR-016 pins this as a hard failure. Enumerating the four combinations once, in one function, makes the invariant auditable and easy to test (one fixture per combination, though only one is enough for acceptance).

**Alternatives considered**: (a) Compute `expected_mrr = (decision == "edge_review_required")` and compare — terser but less self-documenting. (b) Let per-input schema validation catch it — the schemas do not encode this cross-field invariant; a fresh check is required.

## Decision 10 — Fixture strategy

**Decision**: Seven minimal fixture pairs under `tests/fixtures/assembler/`:

| Fixture folder | Purpose | Extractor | Routing |
|---|---|---|---|
| `happy_grounded/` | US1–US5 golden path | Grounded company_name, address (city+state+postal+street), one EIN, email; present=true, inferred=false. | `decision=edge_accept`, `manual_review_required=false`, `review_reason=null`. |
| `missing_name_inferred/` | US4 AS-2 + SC-002 | company_name with present=false, inferred=true, confidence≤0.5; partial address. | `decision=edge_review_required`, `manual_review_required=true`, `review_reason="company_name_inferred"`. |
| `empty_extraction_spam_gate/` | US4 AS-6 | All-null vendor_candidate. | `decision=edge_review_required`, `review_reason="post_extraction_spam_gate_failed"`. |
| `contract_drift/` | US6 AS-4 | Extractor with `contract_set_version = "1.1.0"`. | Routing with `contract_set_version = "1.0.0"`. |
| `document_id_mismatch/` | US6 AS-3 | `document_id = "inv_005"`. | `document_id = "inv_006"`. |
| `routing_contradiction/` | US6 AS-6 (FR-016) | Normal grounded extractor. | `decision=edge_accept` but `manual_review_required=true, review_reason="company_name_inferred"`. |
| `schema_invalid_extractor/` | US6 AS-5 | Extractor JSON missing `status` (required field). | Valid routing. |

Each fixture is a tiny hand-crafted JSON pair (no PDF needed, no preprocess_output needed — the assembler only reads the two JSONs; the trace block names file paths it does not open).

**Rationale**: These seven scenarios cover every acceptance scenario in US1–US6 and every hard-failure branch. Fixtures are committed to the repo so the test suite is hermetic and reviewable. Keeping each fixture minimal (only the fields the assembler actually reads need to be populated realistically; other required schema fields can be filled with schema-satisfying defaults) keeps the diff reviewable.

**Alternatives considered**: (a) Generate fixtures at test time from factory functions — harder to inspect; diffs hide behind code. (b) Reuse real corpus outputs from 005/008 — those features aren't built yet. (c) Property-based testing only — valuable supplement (unit-level) but does not substitute for golden-path fixtures.

## Decision 11 — SC-008 semver-bump governance path

**Decision**: Policy changes to the `overall_vendor_confidence` formula (FR-019) or the `secondary_identifiers_found` ordering (FR-020) MUST be accompanied, in the same commit, by: (a) a bump of `SEMVER` in `src/ledgerlinc_ocr/assembler/version.py`, (b) a new dated entry in the `## Changelog` section of `contracts/stage1_vendor_identity/AMENDMENTS.md` naming the old and new semver and summarizing the policy delta, and (c) an update to the pinned formula text in spec.md FR-019 or FR-020 as appropriate. Reviewers enforce this at PR time; no runtime check is required because SC-008's claim is governance-level, not code-level.

**Rationale**: SC-008 requires that every `final_structured_payload.json` carry the policy generation that produced it (via the semver segment of `pipeline_version`). A commit that changes the formula without bumping `SEMVER` would silently diverge the output value from the carried version string — a reproducibility violation. Binding the three edits together in one commit (version file + AMENDMENTS entry + spec text) makes the governance contract reviewable and searchable.

**Alternatives considered**: (a) A CI hook that greps the diff for `version.py` changes — brittle, prone to false positives/negatives. (b) Encode the formula's hash in `pipeline_version` and recompute at run time — introduces a non-deterministic dependency on source code layout into the output. (c) Leave it informal — SC-008 becomes aspirational and not enforceable.
