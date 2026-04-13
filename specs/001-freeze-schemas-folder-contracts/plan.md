# Implementation Plan: Freeze Schemas & Folder Contracts

**Branch**: `001-freeze-schemas-folder-contracts` | **Date**: 2026-04-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-freeze-schemas-folder-contracts/spec.md`

## Summary

Deliver the frozen stage 1 contract set and its validator. The feature produces two co-versioned layers: (a) the existing human-facing documentation in `docs/stage1-vendor-identity/` plus `.specify/memory/constitution.md`, and (b) a new machine-readable contract layer at `contracts/stage1_vendor_identity/v1.0.0/` consisting of JSON Schema (Draft 2020-12) files for the seven persisted artifacts and the folder contract, plus a contract-set metadata file. Both layers advance together under a single `contract_set_version` (semver, starting at `1.0.0`), which is stamped on every persisted artifact. A Python CLI + module (`src/ledgerlinc_ocr/validator/`) validates artifacts and folders against the contract set, enforcing JSON-Schema-expressible rules via `jsonschema` and cross-artifact rules (company-name provenance triad, document-count consistency, reserved-filename use) via deterministic Python code. The validator emits a canonical machine-readable structured report plus a human-readable CLI rendering, signals pass/fail via exit code, and writes structured reports that the downstream harness can aggregate across the 20-document corpus. No pipeline extraction, routing, or evaluation behavior is delivered by this slice — only the contracts, the validator, and the corpus-folder scaffold that depends on them.

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` base image)
**Primary Dependencies**: `jsonschema >= 4.22` (Draft 2020-12 validator); `pydantic >= 2.7` for the structured-report model and typed CLI results; Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`). No PyTorch, no PaddleOCR, no network dependencies for this slice.
**Storage**: Filesystem only. JSON artifacts on disk. No database. No model weights. No network calls.
**Testing**: `pytest >= 8.2` with fixture-driven good/bad sample artifacts under `tests/contract_tests/fixtures/`. Each rule in the spec (including all cross-artifact rules from FR-035 and FR-019) has at least one positive and one negative test case.
**Target Platform**: Linux (devcontainer + WSL2 host + native Linux ROCm). No OS-specific behavior; pure Python.
**Project Type**: Single-project Python library with a CLI entry point. No service, no UI, no frontend/backend split.
**Performance Goals**: Validate an artifact in under 100 ms; validate the full 20-document corpus (including cross-artifact checks) in under 2 seconds on a modern laptop. Not a primary optimization target — correctness dominates.
**Constraints**: Must run inside the lightweight devcontainer without ROCm, GPU, or Ollama. Must not depend on any other stage 1 component; this slice is explicitly a foundation. Must not introduce any coupling to PaddleOCR, Falcon models, or Ollama.
**Scale/Scope**: 7 artifact contracts + 1 folder contract + 1 contract-set metadata file = 9 machine-readable files under `contracts/stage1_vendor_identity/v1.0.0/`. 39 functional requirements in spec. 20-document test corpus (folder-contract scaffold created as empty placeholders; full labeling is a separate workstream).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution at `.specify/memory/constitution.md` defines five core principles and a set of quality gates. Each is evaluated against this feature:

### I. One Repo, Clear Runtime Boundaries — **PASS**

This feature touches only contracts (documentation + machine-readable schemas) and a validator. It does **not** blur pipeline / harness / model runtime boundaries. The validator is a library + CLI with no model inference, no Ollama dependency, no extraction logic. The folder-contract scaffold is empty; it is populated by labeling (a harness concern) or by the pipeline (a pipeline concern), not by this feature.

### II. Evidence-First, Schema-First Design — **PASS (this is the enabler)**

This feature IS the schema-first enabler. The constitution names the four stage 1 artifacts as authoritative; this feature promotes them to machine-validatable contracts alongside their human-facing documentation. FR-001 through FR-027 enumerate the artifact-level rules; FR-028 through FR-032 enumerate the folder rules; FR-037 through FR-039 enumerate the governance rules that keep the two layers in lockstep.

### III. Deterministic Control Over Model Output — **PASS**

The validator is deterministic Python code over JSON Schema + explicit cross-artifact rules. No model is ever invoked. The validator's decision function is a pure function of (artifact bytes, contract-set version). FR-035 and FR-036 make this explicit.

### IV. Provenance and Review Safety — **PASS**

The company-name provenance triad (`present`, `inferred`, `manual_review_required`) is enforced by:

- FR-019 on `final_structured_payload`
- FR-024 on `expected` for missing-name documents
- FR-035 cross-artifact rule across `expected` / `edge_extraction_output` / `routing_decision` / `final_structured_payload`
- SC-004 as a measurable success criterion

The contract makes it structurally impossible for a conforming artifact to claim an inferred company name without also forcing manual review.

### V. Benchmarkable and Reproducible Delivery — **PASS (indirect)**

This feature does not itself produce evaluation metrics, but it unblocks the harness (spec SC-006) and stamps every artifact and evaluation output with `contract_set_version` so historical results stay interpretable after amendments (FR-005a, FR-037).

### Stage 1 Scope Constraints — **PASS**

- PDF-only: this feature does not read PDFs; the `preprocess_output` contract assumes PDF-derived pages but is neutral at the schema level.
- Vendor identity focus only: `edge_extraction_output` includes invoice header fields (per FR-013) but no line items. No line-item contracts exist.
- No cloud execution path: not applicable.
- Minimal review output: `review_status` limited to `manual_review_required` + `review_reason`.

### Quality Gates — **PASS**

- Gate 1 (pipeline/harness boundary): no blur; both PRDs remain separate.
- Gate 2 (output contracts update `schemas.md`): the machine-readable layer is co-located with `schemas.md` and updated in the same amendment. The plan does not alter `schemas.md` beyond what contract extraction requires for lossless representation; any reconciliation edits are part of amendment `1.0.0`.
- Gate 3 (runtime docs): not touched by this feature.
- Gate 4 (verifiable local execution): covered by the quickstart and test suite.
- Gate 5 (runtime/container changes): N/A.
- Gate 6 (evaluation preserves `expected.json` comparison): preserved — the `expected` contract is the authoritative truth shape.

**Result**: All constitution principles and gates pass. No Complexity-Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/001-freeze-schemas-folder-contracts/
├── spec.md              # Frozen feature specification (already written)
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 decisions (/speckit.plan output)
├── data-model.md        # Phase 1 entities & data structures (/speckit.plan output)
├── quickstart.md        # Phase 1 developer/labeler quickstart (/speckit.plan output)
├── contracts/           # Phase 1 interface contracts for this feature
│   ├── validator-cli.md       # CLI command surface
│   ├── report.schema.json     # Machine-readable validation-report shape
│   └── module-api.md          # Python module API surface
├── checklists/
│   └── requirements.md        # Spec-quality checklist (already written)
└── tasks.md             # Phase 2 output from /speckit.tasks — NOT created by this command
```

### Source Code (repository root)

Single-project Python library + CLI, matching the implementation-plan's recommended structure under `src/ledgerlinc_ocr/`. The machine-readable contract layer lives at repo root `contracts/` per the spec's Clarification 1 (co-located, version-gated).

```text
contracts/
└── stage1_vendor_identity/
    ├── AMENDMENTS.md                           # Human-facing changelog of contract-set version bumps
    └── v1.0.0/
        ├── contract_set.json                   # Version metadata, cross-artifact rule refs, challenge_tags vocabulary
        ├── preprocess_output.schema.json
        ├── edge_extraction_output.schema.json
        ├── routing_decision.schema.json
        ├── final_structured_payload.schema.json
        ├── expected.schema.json
        ├── evaluation_document.schema.json
        ├── evaluation_run_summary.schema.json
        ├── folder.schema.json                  # Per-document and corpus-root folder contract
        └── README.md                           # Machine-layer amendment checklist

src/
└── ledgerlinc_ocr/
    ├── __init__.py
    └── validator/
        ├── __init__.py                         # Public module API (see contracts/module-api.md)
        ├── __main__.py                         # python -m ledgerlinc_ocr.validator entry
        ├── cli.py                              # argparse CLI
        ├── loader.py                           # Loads contract-set v{X.Y.Z} from contracts/
        ├── artifact.py                         # JSON Schema-based artifact validation
        ├── folder.py                           # Folder-layout validation (incl. conditional notes.md)
        ├── cross_artifact.py                   # Provenance triad, doc-count consistency, reserved-filename checks
        ├── report.py                           # ViolationReport + rendering (structured + human)
        └── version.py                          # contract_set_version compatibility checks

tests/
├── stage1_vendor_identity/                     # Runtime corpus root — created here as empty scaffold
│   └── .gitkeep
└── contract_tests/                             # Pytest suite for this feature only
    ├── __init__.py
    ├── fixtures/
    │   ├── good/                               # One conforming sample per artifact + one good folder
    │   │   ├── preprocess_output.json
    │   │   ├── edge_extraction_output.json
    │   │   ├── routing_decision.json
    │   │   ├── final_structured_payload.json
    │   │   ├── expected_explicit_easy.json
    │   │   ├── expected_missing_name.json
    │   │   ├── evaluation_document.json
    │   │   ├── evaluation_run_summary.json
    │   │   └── folder_inv_001_easy/
    │   └── bad/                                # One deliberate-violation sample per rule
    │       ├── empty_string_for_null.json
    │       ├── missing_vote_metadata.json
    │       ├── unknown_challenge_tag.json
    │       ├── tax_id_invalid_type.json
    │       ├── inferred_without_review_required.json
    │       ├── routing_decision_review_reason_null_when_required.json
    │       ├── expected_contains_confidence.json
    │       ├── folder_missing_notes_hard/
    │       ├── folder_missing_notes_easy/      # Should WARN, not FAIL
    │       ├── folder_missing_source_pdf/
    │       └── folder_reserved_filename_collision/
    ├── test_artifact_contracts.py
    ├── test_folder_contract.py
    ├── test_cross_artifact.py
    ├── test_report_shape.py
    ├── test_version_stamping.py
    └── test_cli.py
```

**Structure Decision**: Single-project Python layout with the machine-readable contract layer at `contracts/stage1_vendor_identity/v{X.Y.Z}/` (repo-root, co-located with `docs/` and `src/`). This placement matches the spec's Clarification 1 — the machine layer is co-located with the human layer and both are updated together through the amendment path. The validator lives at `src/ledgerlinc_ocr/validator/` as the first module populated in the `src/ledgerlinc_ocr/` tree recommended by the implementation plan; later pipeline modules (`preprocess/`, `extract/`, `routing/`, `evaluate/`) will be added next to it by subsequent features without re-home. The runtime corpus root `tests/stage1_vendor_identity/` is created empty; pytest tests live in a sibling directory `tests/contract_tests/` to avoid conflict.

## Complexity Tracking

No constitutional violations. Table intentionally empty.
