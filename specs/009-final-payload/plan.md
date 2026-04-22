# Implementation Plan: Final Structured Payload Assembly (009-final-payload)

**Branch**: `009-final-payload` | **Date**: 2026-04-21 | **Spec**: [`spec.md`](./spec.md)
**Input**: Feature specification from `/specs/009-final-payload/spec.md`

## Summary

A deterministic, artifact-to-artifact assembler that reads one per-document folder's
`edge_extraction_output.json` (005) and `routing_decision.json` (008) and writes
`final_structured_payload.json` conforming to the frozen v1.0.0 contract. The stage flattens
`{value, confidence, evidence}` down to `{value, confidence}` (no evidence in the downstream
payload), copies `review_status` verbatim from routing, computes a pinned `quality_summary`
roll-up (stage 1 policy `0.1.0`: `clip(0.5 * company_name.confidence + 0.5 * mean(secondary
identifier confidences, default 0.0), 0.0, 1.0)` with `secondary_identifiers_found` emitted in
schema-enum order), and populates a relative-path `trace` block. Six cross-input invariants
(missing input, unreadable input, schema-invalid input, contract drift, `document_id`
mismatch, routing `decision` vs. `review_status` contradiction) are hard failures — exit
non-zero, no output written. A seventh invariant validates the assembled output against the
frozen v1.0.0 schema before writing; see `data-model.md` §Cross-input invariant table. No model calls, no network, no mutation of inputs. CLI is `python -m
ledgerlinc_ocr.assembler`, paralleling the existing `validator` and `preprocessing` slices.

## Technical Context

**Language/Version**: Python 3.12 (matches devcontainer base image and existing `ledgerlinc-ocr` package)
**Primary Dependencies**: `jsonschema >= 4.22` (already installed; used for schema validation via the existing `ledgerlinc_ocr.validator.artifact` loader), `pydantic >= 2.7` (already installed; used for typed internal result objects), Python stdlib (`argparse`, `json`, `pathlib`, `datetime`, `dataclasses`). No new runtime dependencies.
**Storage**: Filesystem only. Reads `<per-doc-folder>/edge_extraction_output.json` and `<per-doc-folder>/routing_decision.json`. Writes `<per-doc-folder>/final_structured_payload.json`. Trace block references `source.pdf` and `preprocess_output.json` by relative path but does not read them.
**Testing**: `pytest >= 8.2` (existing). Contract tests under `tests/contract_tests/`, feature-level pipeline tests under `tests/pipeline_tests/`, fixtures under `tests/fixtures/assembler/`. Test-time network isolation already enforced by `pytest-socket` per the existing preprocessing convention.
**Target Platform**: Linux (devcontainer) and native Linux. No OS-specific code.
**Project Type**: CLI library — new submodule `src/ledgerlinc_ocr/assembler/` alongside the existing `preprocessing/`, `pipeline/`, and `validator/` packages.
**Performance Goals**: ≤ 200 ms wall-clock per document on a developer workstation (SC-001). Two JSON reads + one JSON write + deterministic Python arithmetic; not a CPU-bound path.
**Constraints**: Byte-identical output across runs (except `processed_at`) per FR-022 and SC-004. Zero `evidence` keys in output per FR-014 and SC-003. No network, no model calls, no mutation of inputs (FR-023, FR-024). All four trace paths are relative (FR-021). Hard-fail on contract drift, `document_id` mismatch, routing contradiction, missing inputs, and schema-invalid inputs (FR-003–FR-005, FR-016).
**Scale/Scope**: One invocation per document; 20 corpus documents total in stage 1. Corpus-level orchestration lives outside this feature (in the harness per 006/007).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Gate | Assessment |
|---|---|
| **I. One Repo, Clear Runtime Boundaries** | ✅ This feature is pipeline code only. It owns "final payload assembly" (the constitution names this explicitly). Does not touch the harness, the corpus, the evaluator, or model runtime. |
| **II. Evidence-First, Schema-First Design** | ✅ Consumes two frozen-contract artifacts, emits the fourth authoritative stage 1 artifact (`final_structured_payload`). Every output is machine-validated against `contracts/stage1_vendor_identity/v1.0.0/final_structured_payload.schema.json` before the file is written. Contracts are not modified — the frozen v1.0.0 set is sufficient. |
| **III. Deterministic Control Over Model Output** | ✅ Zero model calls. The five cross-input invariants, the `quality_summary` derivation, the evidence-flattening, the `review_status` verbatim propagation, and the FR-016 contradiction trap are all pure deterministic code. Confidence signals are propagated, not authoritative. |
| **IV. Provenance and Review Safety** | ✅ `company_name.present` and `company_name.inferred` are propagated verbatim from the extractor (FR-009). `review_status.review_reason` (including the canonical string `"company_name_inferred"`) is propagated verbatim from routing (FR-015). The assembler never recomputes provenance. |
| **V. Benchmarkable and Reproducible Delivery** | ✅ Byte-identical output except `processed_at` (SC-004). Policy changes (formula/ordering) are visible via the `<semver>` segment of `pipeline_version` (FR-007, SC-008). The assembler is runnable per-document and, in aggregation with 003/005/008, closes the one-document end-to-end path (SC-010). |
| **Stage 1 Scope Constraints** | ✅ Invoice-only (`document_type == "invoice"` hard-coded per FR-008); no line items (FR-013 excludes `invoice_header_fields`); no cloud path (FR-023); no latency gate (SC-001 is an internal target, not a release gate); `consensus_level == "single_voter_baseline"` hard-coded (FR-017). |
| **Quality Gate 1** (pipeline/harness boundary) | ✅ Code lives under `src/ledgerlinc_ocr/assembler/`; tests live under `tests/pipeline_tests/`, `tests/contract_tests/`, and `tests/fixtures/assembler/`. No harness files touched. |
| **Quality Gate 2** (output-contract changes update `schemas.md`) | ✅ No schema changes. The frozen v1.0.0 `final_structured_payload.schema.json` is sufficient for this feature. `docs/stage1-vendor-identity/schemas.md` is unchanged. |
| **Quality Gate 3** (runtime behavior changes) | N/A — no runtime/container changes. |
| **Quality Gate 4** (verifiable via at least one local execution path) | ✅ CLI `python -m ledgerlinc_ocr.assembler --document-folder <path>`; quickstart documents the run. |
| **Quality Gate 5** (runtime/container changes) | N/A. |
| **Quality Gate 6** (evaluation changes) | N/A — this feature produces the input the evaluator consumes, but does not change how the evaluator compares to `expected.json`. |

**Result**: All principles and gates pass. No violations to justify; Complexity Tracking section stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-final-payload/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature spec with Clarifications section (from /speckit.clarify)
├── research.md          # Phase 0 output — see below for Decisions 1–10
├── data-model.md        # Phase 1 output — entities, flattening rules, derivation formulas
├── contracts/
│   ├── module-api.md    # Importable Python API stability contract
│   └── cli-contract.md  # `python -m ledgerlinc_ocr.assembler` flags and exit codes
├── quickstart.md        # End-to-end walkthrough (stage fixtures → run → validate)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/ledgerlinc_ocr/
├── assembler/                      # NEW — this feature
│   ├── __init__.py                 # Public surface: Invocation, run, build_pipeline_version
│   ├── __main__.py                 # `python -m ledgerlinc_ocr.assembler` entry
│   ├── cli.py                      # argparse entry (mirrors preprocessing/cli.py)
│   ├── pipeline.py                 # Invocation dataclass + run() orchestrator
│   ├── errors.py                   # EXIT_* constants + exception classes (mirror preprocessing/errors.py)
│   ├── version.py                  # SEMVER="0.1.0", SLICE_PREFIX="009-final-payload", build_pipeline_version()
│   ├── flatten.py                  # Evidence-stripping: company_name, address, tax_ids, contacts
│   ├── quality.py                  # quality_summary derivation: formula, explicit_name_found, secondary_identifiers_found
│   ├── validation.py               # Cross-input invariants: contract drift, document_id match, routing contradiction
│   ├── trace.py                    # Trace block builder (four relative paths)
│   └── write.py                    # Deterministic JSON write (sorted keys, fixed indent, trailing newline)
│
├── preprocessing/                  # (existing, unchanged)
├── pipeline/                       # (existing — may later add an assembler stage wrapper)
└── validator/                      # (existing — reused for per-input schema validation)

tests/
├── contract_tests/                 # (existing — verify schema-level guarantees)
│   └── test_final_payload_contract_tie_in.py   # NEW — asserts assembler output validates
├── pipeline_tests/                 # (existing — feature-level behavioral tests)
│   ├── test_assembler_us1_happy_path.py        # NEW — schema-valid payload, all top-level keys
│   ├── test_assembler_us2_flatten.py           # NEW — evidence stripped, present/inferred preserved
│   ├── test_assembler_us3_review_status.py     # NEW — review_reason verbatim including canonical string
│   ├── test_assembler_us4_quality_summary.py   # NEW — formula, explicit_name_found, secondary order
│   ├── test_assembler_us5_trace.py             # NEW — relative paths resolve
│   ├── test_assembler_us6_hard_failures.py     # NEW — six failure fixtures (inc. FR-016)
│   └── test_assembler_cli.py                   # NEW — CLI argparse, exit codes, stderr JSON
├── fixtures/
│   └── assembler/                              # NEW — minimal extractor+routing fixtures per scenario
│       ├── happy_grounded/
│       │   ├── edge_extraction_output.json
│       │   └── routing_decision.json
│       ├── missing_name_inferred/
│       ├── empty_extraction_spam_gate/
│       ├── contract_drift/
│       ├── document_id_mismatch/
│       ├── routing_contradiction/
│       └── schema_invalid_extractor/
└── unit/                                       # (existing — optional unit-level tests for pure helpers)
    └── test_assembler_quality_formula.py       # NEW — unit-level formula tests
```

**Structure Decision**: Single-project layout matching the existing `ledgerlinc_ocr` package conventions (`preprocessing/`, `pipeline/`, `validator/` all follow the same module shape). New submodule `src/ledgerlinc_ocr/assembler/` mirrors the `preprocessing/` layout (cli.py + pipeline.py + errors.py + version.py + narrow helper modules). Tests live in the existing `tests/pipeline_tests/` and `tests/contract_tests/` directories; fixtures in `tests/fixtures/assembler/`.

## Phase 0: Research (Decisions)

See [`research.md`](./research.md). Eleven decisions resolved:

1. **JSON write determinism** — fixed indent, sorted top-level keys per a pinned key-order table (schema order), trailing newline, UTF-8.
2. **`processed_at` format** — `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`.
3. **`pipeline_version` format** — `"009-final-payload@0.1.0"` (spec clarification).
4. **Schema validation reuse** — import `ledgerlinc_ocr.validator.artifact.load_and_validate` for per-input validation; do not reinvent.
5. **Exit codes** — follow the existing preprocessing convention (`0` ok, `1` unexpected, `2` input rejected, `3` internal). Contradiction/drift/mismatch all map to `2`.
6. **Rounding of `overall_vendor_confidence`** — compute in Python floats, then round to 4 decimal places via `round(value, 4)` before writing, to eliminate platform-level float drift in byte-identical comparison.
7. **Evidence stripping shape** — a single declarative `FIELDS_TO_FLATTEN` table drives per-field copy; no ad-hoc per-field code.
8. **Secondary identifiers derivation** — `"address"` uses routing's `address_has_minimum_components` definition (city + state + postal_code all non-null with non-empty evidence), but the assembler re-derives this locally from the extractor rather than reading routing's `checks` block, to keep the two signals independent (FR-020).
9. **FR-016 contradiction detection** — compute `expected_manual_review = (decision == "edge_review_required")` and `expected_review_reason_is_string = (decision == "edge_review_required")`; any mismatch between expected and actual `review_status` raises `RoutingContradictionError`.
10. **Fixture strategy** — seven minimal, hand-crafted fixture pairs (happy grounded, missing-name inferred, spam-gate empty, contract drift, document-id mismatch, routing contradiction, schema-invalid). Each pair is schema-valid for its intended test (except the drift/contradiction/schema-invalid cases which intentionally violate on exactly one axis).
11. **SC-008 semver-bump governance path** — a formula/ordering change must land in one commit together with a `SEMVER` bump in `version.py`, an entry in `contracts/stage1_vendor_identity/AMENDMENTS.md`, and the updated spec text. Enforced at PR review, not at runtime.

## Phase 1: Design & Contracts

Outputs:

- [`data-model.md`](./data-model.md) — entities: `Invocation`, `AssemblerInputs`, `FlattenedVendorCandidate`, `QualitySummary`, `TraceBlock`, `FinalPayload`. Includes the `FIELDS_TO_FLATTEN` table, the `quality_summary` derivation pseudocode, and the cross-input invariant table.
- [`contracts/module-api.md`](./contracts/module-api.md) — stability contract for the importable Python API (`from ledgerlinc_ocr.assembler import Invocation, run, build_pipeline_version`). Specifies allowed signature changes under semver.
- [`contracts/cli-contract.md`](./contracts/cli-contract.md) — stability contract for `python -m ledgerlinc_ocr.assembler`: flags, exit codes, stderr format. Mirrors the preprocessing CLI contract.
- [`quickstart.md`](./quickstart.md) — end-to-end walkthrough: install, stage a fixture, run, validate output.

Agent context update: run `.specify/scripts/bash/update-agent-context.sh claude` after the artifacts are written.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. No entries.
