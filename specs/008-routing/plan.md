# Implementation Plan: Deterministic Routing (Stage 1 Vendor-Identity)

**Branch**: `008-routing` | **Date**: 2026-04-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-routing/spec.md`

## Summary

Build the stage 1 deterministic router: one per-document folder in, one
schema-valid `routing_decision.json` out. The router reads
`edge_extraction_output.json` (produced by the upstream extractor, frozen at
`contract_set_version = "1.0.0"`), applies pure rule-based code — missing-name
gate, post-extraction spam gate, secondary-identifier floor, upstream-failure
propagation, priority-ordered review reasons — and writes a schema-valid
`routing_decision.json` alongside the input. No model calls, no OCR, no
`preprocess_output.json` re-read: routing is artifact-to-artifact.

The slice is deterministic by construction: two runs against the same input
produce byte-identical output except for `processed_at`. Scores are pure
structural grounding fractions (no confidence), per the 2026-04-21
clarifications. Canonical review-reason strings are pinned by `policy_version`,
including the load-bearing `"company_name_inferred"` string consumed by the
forthcoming evaluator (007).

## Technical Context

**Language/Version**: Python 3.12 (matches devcontainer; matches 001/002/003 slices)
**Primary Dependencies**:
- Existing: `jsonschema>=4.22,<5`, `pydantic>=2.7,<3` (already in `pyproject.toml`)
- **Reused in-repo**: `ledgerlinc_ocr.validator` — to validate both the input
  `edge_extraction_output.json` and the assembled `routing_decision.json`
  against the frozen `v1.0.0` schemas. No new third-party dependency is
  introduced by this slice.
- **No new dependencies**. Routing is pure Python stdlib + `jsonschema` via the
  existing validator module.
**Storage**: Filesystem only. Reads `<per-document-folder>/edge_extraction_output.json`,
writes `<per-document-folder>/routing_decision.json`. No DB, no network, no
other file in the folder is read or written.
**Testing**: `pytest` under the existing `tests/contract_tests/` harness plus
new `tests/unit/router/` and `tests/integration/router/` trees. Integration
fixtures are hand-authored JSON files (not model runs) so the router can be
tested independently of the extractor's runtime status.
**Target Platform**: Linux (devcontainer, native WSL Ubuntu 24.04). CPU only.
No GPU, no cloud, no host Ollama involvement.
**Project Type**: Single Python package — extends `src/ledgerlinc_ocr/` with a
new `router/` module, invokable as `python -m ledgerlinc_ocr.router route
<folder>` (pinned by spec FR-025, clarification Q4).
**Performance Goals**: ≤ 200 ms wall-clock per document on a developer
workstation (SC-001). Trivially satisfied by pure rule-based code over one
small JSON file; not a release gate, but observed.
**Constraints**:
- Byte-identical `routing_decision.json` across reruns excluding `processed_at`
  (FR-021, SC-004).
- Artifact MUST validate against frozen contract `v1.0.0` before any write
  (FR-002, SC-001).
- No model calls, no OCR, no `preprocess_output.json` re-read (FR-019).
- Hard errors on missing / schema-invalid / version-drifted input (FR-003,
  SC-006). No partial `routing_decision.json` ever persisted on failure.
- Canonical review-reason strings are part of `policy_version`; changing any
  of them bumps `policy_version` (FR-005, FR-015, SC-010).
**Scale/Scope**: 20-document stage 1 corpus (5 easy / 5 medium / 5 hard /
5 missing_name). One document per invocation. Corpus-level orchestration is
the harness's responsibility (constitution §V), not this feature's.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.0.0:

| Principle | Gate | Status |
|-----------|------|--------|
| I. One Repo, Clear Runtime Boundaries | Routing belongs to the pipeline layer; must not bundle harness, extraction, or final-payload concerns; must not embed model runtime. | **PASS** — `src/ledgerlinc_ocr/router/` is pipeline code only. Reads one JSON, writes one JSON (FR-001, FR-022). No model runtime, no Ollama calls (FR-019). Harness / evaluator remain separate. |
| II. Evidence-First, Schema-First Design | Artifact MUST validate against the frozen `routing_decision` contract; prompts/code adapt to the schema, not the reverse. | **PASS** — FR-002 mandates schema validation before persist. No schema amendment needed; `contract_set_version = "1.0.0"` is consumed as-is. Input is also validated against `edge_extraction_output.schema.json` before any rule fires (FR-003). |
| III. Deterministic Control Over Model Output | Spam gate, review-required decisions, routing policy must be deterministic code — confidence is a signal, not a substitute for provenance. | **PASS** — Every rule is pure code (FR-013, FR-014, FR-008, FR-015). Confidence is explicitly excluded from all gates and all scores (FR-017, FR-018, clarification Q1). The router never calls a model (FR-019). |
| IV. Provenance and Review Safety | Inferred company names MUST force `manual_review_required = true`. Non-negotiable. | **PASS** — FR-008 wires the constitutional invariant directly: `company_name.inferred == true` OR `company_name.present == false` forces `decision = "edge_review_required"` AND `review_reason = "company_name_inferred"` exactly. SC-002 + SC-008 make this a release gate. |
| V. Benchmarkable and Reproducible Delivery | One-document end-to-end execution; per-document folder layout preserved. | **PASS** — CLI processes one document, writes artifact next to `edge_extraction_output.json` (FR-001). Quickstart captures the one-command devcontainer path. Corpus orchestration is deferred to the harness (assumption, constitution §V). |

**Stage 1 Scope Constraints** (constitution §"Stage 1 Scope Constraints"):
- PDF input only ✓ (this slice consumes the extractor's JSON output; PDF input is handled upstream by 003)
- Vendor identity focus ✓ (all rules gate on `vendor_candidate` fields; `invoice_header_fields` are ignored by the router)
- No line-item extraction ✓ (router does not read or emit line items)
- No cloud execution ✓ (FR-019)
- No latency gate ✓ (SC-001's 200 ms target is a soft sanity check, not a release gate)

**Quality Gates** (constitution §"Quality Gates"):
1. Pipeline vs. harness boundary preserved — this slice is pipeline-only; the evaluator (007) and final-payload (future) are separate slices and their work does not land here.
2. Output contracts unchanged — this slice consumes the frozen `routing_decision` schema; no schema edits required. `docs/stage1-vendor-identity/schemas.md` already matches.
3. Runtime behavior — this slice does not change the Ollama runtime story; `ollama-runtime.md` requires no update.
4. Verifiable through concrete local execution — CLI `python -m ledgerlinc_ocr.router route <folder>` against a fixture.
5. Runtime/container changes — none (existing `pipeline-dev` devcontainer is sufficient).
6. Evaluation comparison preserved — this slice does not modify evaluation; the harness still compares `final_structured_payload.json` to `expected.json`. The evaluator (007) will consume this router's output.

**Result: PASS. No constitution violations. Complexity Tracking section left empty.**

### Post-Phase 1 re-check

Re-evaluated after drafting `research.md`, `data-model.md`, `contracts/cli-contract.md`, and `quickstart.md`:

- Phase 0/1 introduced zero new third-party dependencies — stdlib + existing `ledgerlinc_ocr.validator` only (research Decision 1). Principle I boundary preserved.
- All derived entities in `data-model.md` are pure functions of the input dict; no state, no model calls. Principle III preserved.
- `policy_version` semver scheme (Decision 3) and pinned canonical/affirmative/informational reason strings (Decisions 9–10) make Principle II's schema-first + policy-bump-on-change rules mechanical.
- Principle IV (company-name provenance) is wired directly into the rule table (`missing_name`, priority 1) with canonical string `"company_name_inferred"` pinned as part of `policy_version`.
- Principle V (reproducibility) is satisfied by `quickstart.md`'s one-document walk-through and the determinism diff in §4.

No principles moved; no violations introduced; **Complexity Tracking still empty**.

## Project Structure

### Documentation (this feature)

```text
specs/008-routing/
├── plan.md              # This file
├── spec.md              # Feature specification (already exists)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # CLI surface (artifact shape is inherited from frozen v1.0.0 schema)
├── checklists/          # Existing (spec-kit checklists)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/ledgerlinc_ocr/
├── __init__.py                          # existing
├── validator/                           # existing — contract validator (reused for input + output validation)
├── preprocessing/                       # existing — 003 slice
└── router/                              # NEW — this slice
    ├── __init__.py
    ├── __main__.py                      # `python -m ledgerlinc_ocr.router`
    ├── cli.py                           # argparse entry point; `route` subcommand
    ├── pipeline.py                      # orchestrates load → validate input → compute checks → compute scores → apply rules → assemble → validate output → write
    ├── input_loader.py                  # read + schema-validate edge_extraction_output.json; raises typed errors on missing / malformed / version-drift
    ├── checks.py                        # pure functions for the 6 `checks` booleans (FR-009 – FR-013)
    ├── scores.py                        # pure functions for the 5 `scores` numbers (FR-017 canonical formulas, clarification Q2)
    ├── rules.py                         # rule evaluation: missing-name, spam-gate, secondary-identifier floor, upstream-failure; returns (decision, review_reason, firing_rule_ids)
    ├── reasons.py                       # assemble the `reasons` array in the pinned FR-015 priority order (clarification Q3); map rule IDs to canonical reason strings + human-readable affirmatives
    ├── artifact.py                      # assemble routing_decision dict; validate against v1.0.0 schema before returning; atomic write via temp-file + rename
    ├── errors.py                        # typed errors: MissingInputError, MalformedInputError, VersionDriftError, ContractAssertionError
    └── version.py                       # pipeline_version builder + POLICY_VERSION constant (FR-005)

tests/
├── contract_tests/                      # existing
├── unit/router/                         # NEW
│   ├── test_checks.py                   # one test per `checks` boolean across grounded / null / partial inputs
│   ├── test_scores.py                   # verify canonical formulas exactly (clarification Q2); boundary cases (all null → 0.0; all grounded → 1.0)
│   ├── test_rules.py                    # rule firing matrix: missing-name, spam-gate, secondary-identifier-floor, upstream-failure, and their interactions (priority order)
│   ├── test_reasons.py                  # reasons array ordering invariant (clarification Q3); canonical string exactness
│   ├── test_artifact.py                 # atomic-write; schema-invalid dict rejected before write; no partial file on failure
│   ├── test_input_loader.py             # missing / unreadable / schema-invalid / version-drifted input; each produces its own typed error
│   └── test_version.py                  # pipeline_version shape; POLICY_VERSION non-empty
├── integration/router/                  # NEW — per-story files; one test per acceptance scenario
│   ├── test_us1_schema_valid.py         # US1 AC#1 + AC#2
│   ├── test_us1_consensus_summary.py    # US1 AC#3
│   ├── test_us1_decision_review_status_consistency.py  # US1 AC#4
│   ├── test_us1_reasons_traceability.py # US1 AC#5
│   ├── test_us1_determinism.py          # US1 AC#6 — byte-identical except processed_at
│   ├── test_us1_no_side_effects.py      # US1 AC#7 — no writes outside folder; inputs untouched
│   ├── test_us2_missing_name_canonical_string.py  # US2 AC#1, AC#2, AC#3 — "company_name_inferred" exact
│   ├── test_us2_missing_name_vs_strong_secondaries.py  # US2 AC#4
│   ├── test_us2_edge_accept_requires_explicit_name.py  # US2 AC#5
│   ├── test_us3_secondary_identifier_floor.py          # US3 AC#1 – AC#3
│   ├── test_us3_address_minimum_components.py          # US3 AC#4
│   ├── test_us3_tax_id_floor.py                        # US3 AC#5
│   ├── test_us3_priority_order.py                      # US3 AC#6
│   ├── test_us4_post_extraction_spam_gate.py           # US4 AC#1 + AC#2 + AC#5
│   ├── test_us4_spam_gate_policy_version.py            # US4 AC#3
│   ├── test_us4_priority_over_spam_gate.py             # US4 AC#4
│   ├── test_us5_partial_input.py                       # US5 AC#1, AC#2
│   ├── test_us5_failure_input.py                       # US5 AC#3
│   ├── test_us5_hard_errors.py                         # US5 AC#4 + AC#5 — missing, schema-invalid, version-drift exits non-zero, no artifact
│   ├── test_us5_schema_valid_on_bad_input.py           # US5 AC#5 — failure status still produces schema-valid artifact
│   ├── test_us5_reconstruction.py                      # US5 AC#6 — decision reconstructible from artifact alone
│   ├── test_extractor_invariant_violation.py           # FR-024 — forbidden combos treated as contract violation; defensive review-required
│   └── test_no_model_no_cloud.py                       # FR-019 — router is network-free and model-free
└── fixtures/router/                     # NEW — hand-authored minimal edge_extraction_output.json samples
    ├── clean_explicit_name_full_identity.json          # green path: edge_accept
    ├── missing_name_inferred.json                      # US2 canonical
    ├── missing_name_with_strong_secondaries.json       # US2 AC#4
    ├── explicit_name_zero_secondaries.json             # US3 AC#1
    ├── explicit_name_one_secondary.json                # US3 AC#2
    ├── explicit_name_two_secondaries.json              # US3 AC#3 — edge_accept
    ├── all_null_spam.json                              # US4 canonical
    ├── partial_upstream.json                           # US5 AC#2
    ├── failure_upstream.json                           # US5 AC#3
    ├── version_drift.json                              # US5 AC#5 — contract_set_version != "1.0.0"
    └── forbidden_present_true_inferred_true.json       # FR-024
```

**Structure Decision**: Single-project Python package. The new slice lives under
`src/ledgerlinc_ocr/router/` to sit alongside the existing `validator/` and
`preprocessing/` packages, preserving the "pipeline code owns routing" boundary
from the constitution. The CLI is exposed both as a module (`python -m
ledgerlinc_ocr.router route <folder>`, pinned by clarification Q4) and via a
`route` subcommand to leave room for future subcommands (e.g., corpus mode)
without renaming. Tests split into `unit/` (pure functions over dict inputs —
no filesystem beyond the validator) and `integration/` (fixture JSON →
full CLI → schema validation → output inspection).

The router has **no new third-party dependency**: all behavior is expressible in
stdlib + the existing `jsonschema` validator. This keeps the slice small,
reviewable, and trivially reproducible across environments.

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.
