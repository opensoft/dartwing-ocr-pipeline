# Phase 0 Research: Freeze Schemas & Folder Contracts

**Feature**: `001-freeze-schemas-folder-contracts`
**Date**: 2026-04-12
**Status**: Complete — all `NEEDS CLARIFICATION` markers resolved.

The feature specification's Clarifications section already resolved the five user-facing ambiguities. The Technical Context in `plan.md` raises an additional set of implementation-layer choices that this document pins down.

---

## R1. Machine-readable schema format

**Decision**: JSON Schema Draft 2020-12 is the canonical machine-readable form.

**Rationale**:
- Clarification 1 explicitly calls the machine layer "co-located" and refers to one schema per artifact. JSON Schema is the lingua franca for that concept.
- JSON Schema is language-neutral. Stage 1 is Python-first, but the investigator agent, the future cloud path, and any harness reporting tooling may be written in other languages. Pydantic exports can reproduce JSON Schema, but the reverse is only partial.
- The constitution's quality gates require the documentation layer and the machine layer to always match; JSON Schema is the closest machine-readable analog of the hand-written field tables in `docs/stage1-vendor-identity/schemas.md`. Review diffs stay readable.
- Draft 2020-12 specifically provides `$defs`, `unevaluatedProperties`, `$dynamicRef`, and `dependentRequired`, all of which are needed for the stage-1 rules (see R3).

**Alternatives considered**:
- **Pydantic-as-SSOT with generated JSON Schema exports**: rejected. Pins stage 1 contracts to a Python runtime and couples contract evolution to Pydantic's JSON-Schema generator, which changes shape across Pydantic releases. The constitution's principle that "documentation is SSOT" is easier to preserve when the machine layer is a plain data file, not generated code.
- **Hand-written Python dataclasses only**: rejected. Not machine-readable outside Python; not reviewable by non-implementers; poor fit for the labeling workflow where a labeler must understand the `expected.json` shape without reading code.
- **OpenAPI / AsyncAPI schemas**: rejected. Designed for service endpoints, not persisted artifacts; adds indirection.

---

## R2. JSON Schema validator library

**Decision**: `jsonschema >= 4.22` (the reference Python implementation) using the explicit `Draft202012Validator`.

**Rationale**:
- Pure Python; no native extensions; works inside the minimal devcontainer without additional system packages.
- Draft 2020-12 support is first-class (via `Draft202012Validator`), and `iter_errors()` returns structured `ValidationError` objects that carry `path`, `schema_path`, `validator`, and `message` — exactly the fields needed to build the `violation_code` / `field_path` / `expected` columns of the structured report (FR-036a).
- Actively maintained; widely adopted in the Python ecosystem; test-friendly.

**Alternatives considered**:
- **`fastjsonschema`**: faster, but compiles validators per schema and returns only the first violation by default. The spec (FR-033) requires "an itemized list of violations", and `fastjsonschema` does not enumerate multiple errors as cleanly as `jsonschema.iter_errors()`. Performance is a non-goal for 20 documents.
- **`jsonschema-rs`**: Rust-backed, faster still, but adds a native build dependency that complicates the devcontainer and WSL-vs-Linux parity.
- **Rolling our own validator**: rejected — all effort, no payoff.

---

## R3. Expressing cross-artifact and conditional rules

**Decision**: Two-tier rule implementation.

- **Tier 1 — In-schema rules (JSON Schema)**: all rules that are local to a single artifact and expressible in Draft 2020-12.
  - Type, nullability, required-field, enum (including `decision`, `difficulty`, per-field result values, `challenge_tags` closed vocabulary, reserved tax-ID types, consensus mode).
  - Conditional-within-artifact rules via `if` / `then` / `else`, `dependentRequired`, `dependentSchemas`. Example: inside `routing_decision`, require `review_reason` to be non-null when `manual_review_required = true` (FR-017) — expressed as `if: {properties: {review_status: {properties: {manual_review_required: {const: true}}}}}, then: {properties: {review_status: {properties: {review_reason: {type: string}}}}}`.
  - Stable-identifier patterns for block/OCR-line IDs (FR-008) via `pattern` on strings.
- **Tier 2 — Python-code rules (in `src/dartwing_ocr/validator/cross_artifact.py`)**: rules that span multiple artifacts or require comparing file contents.
  - Company-name provenance triad across `expected`, `edge_extraction_output`, `routing_decision`, `final_structured_payload` (FR-035, SC-004).
  - `evaluation_run_summary.document_count` equals `len(documents)` (edge case #9).
  - Evidence-reference consistency: every `evidence` ID in `edge_extraction_output` must resolve to a block or OCR line ID in `preprocess_output` (FR-008 forward compatibility).
  - Folder-layout rules that depend on `expected.json.difficulty` to pick `notes.md` strictness (FR-029, clarification 5).
  - `contract_set_version` compatibility check (FR-037).
  - Reserved filename collisions in a per-document folder (FR-032).

**Rationale**: JSON Schema Draft 2020-12 cannot express "fields in document A must match fields in document B." Forcing it into a mega-schema or bespoke `$ref` chains obscures intent. Python rules that operate on already-loaded and already-Tier-1-validated artifacts are simpler, testable in isolation, and produce the same `ViolationReport` output shape.

**Alternatives considered**:
- **Single mega-schema combining all artifacts**: rejected. Breaks the "one schema per artifact" intent from Clarification 1, and the triad rule is trivially expressible in Python but tortured in JSON Schema.
- **JSON Logic / CEL / Rego sidecars**: rejected. Adds an engine; Python is already the implementation language.

---

## R4. Contracts directory layout and versioning

**Decision**: `contracts/stage1_vendor_identity/v{MAJOR.MINOR.PATCH}/` with one schema file per artifact + a `contract_set.json` metadata file + a machine-layer `README.md` + an `AMENDMENTS.md` at `contracts/stage1_vendor_identity/` root.

- `contract_set.json` enumerates:
  - `contract_set_version` (semver),
  - each schema file's relative path and the artifact it describes,
  - the closed `challenge_tags` vocabulary (sourced from `dataset-layout.md`),
  - the list of cross-artifact rule identifiers that Tier 2 code must enforce for this version,
  - the folder-contract reference.
- `AMENDMENTS.md` is a human-readable changelog. Each amendment records: old version → new version, what changed, which artifacts or folder rules are affected, and links to the relevant commit or PR.
- The versioned subdirectory (`v1.0.0/`) keeps historical contract sets discoverable. The validator loads the version that `contract_set_version` on an artifact declares.

**Rationale**:
- Versioned subdirectories are the simplest way to make historical artifacts re-validatable without Git archaeology. SC-005 requires that in-flight stage 1 runs all pin a version; SC-008 requires forward compatibility to ensemble mode through a version bump, not a rewrite. The subdirectory layout supports both.
- `contract_set.json` gives the validator a single load point per version and makes the vocabulary + cross-rule list explicit data rather than implicit code.
- Semver starting at `1.0.0` matches the constitution's versioning style (`Version: 1.0.0`) and the clarification answer verbatim.

**Alternatives considered**:
- **Flat `contracts/` with file-level version fields**: rejected. Harder to archive previous versions; merge conflicts on every amendment.
- **Git tags as the version source**: rejected. Ties validation to the checked-out commit rather than to the artifact's stamped `contract_set_version`.

---

## R5. Validator CLI packaging and invocation

**Decision**: Expose the validator as `python -m dartwing_ocr.validator` with subcommands. No installed console script for stage 1 (can be added later via `pyproject.toml` without breaking anything).

Subcommands:
- `validate artifact <path> --contract <name> [--contract-set-version <ver>]`
- `validate folder <path> [--contract-set-version <ver>]`
- `validate corpus <root> [--contract-set-version <ver>]`
- `show contract-set [--version <ver>]` (prints JSON describing the loaded contract set for developers/labelers)

Every subcommand supports `--json` (structured report to stdout) and `--text` (human-readable rendering, default). Exit codes: `0` pass, `1` validation failure (violations), `2` usage error, `3` internal error.

**Rationale**:
- `python -m` works immediately inside the devcontainer with no install step, which matches the lightweight-devcontainer constraint in the constitution.
- Subcommands keep the CLI contract (documented in `contracts/validator-cli.md`) small and stable.
- The separate `--json` / `--text` flags satisfy FR-036 (structured report + human rendering, both derived from the same underlying result). Default to text so labelers see readable output; the harness always passes `--json`.

**Alternatives considered**:
- **Click-based installed script**: rejected for stage 1 because it adds a packaging step without adding function. Can be layered on later.
- **FastAPI HTTP endpoint**: rejected explicitly by the implementation-plan ("start as a Python-first module and CLI, not as a service").

---

## R6. Amendment path — where it lives, what it requires

**Decision**: The amendment path is documented in two places that cross-reference each other:

1. `contracts/stage1_vendor_identity/AMENDMENTS.md` — changelog + the step-by-step amendment checklist (what to edit, in what order, what gates to pass).
2. `.specify/memory/constitution.md` — referenced from the "Governance > Amendment rules" section already present in the constitution (no new section required; the constitution already mandates that amendments be committed with a clear reason).

Required steps for an amendment:
1. Update the human-facing canonical documentation (`docs/stage1-vendor-identity/schemas.md` and/or `dataset-layout.md`, `scoring.md`, `architecture.md`, `constitution.md` — whichever is affected).
2. Create a new `contracts/stage1_vendor_identity/v{X.Y.Z}/` directory (or edit the current one for patch/in-review amendments that have not yet shipped).
3. Update the validator's cross-artifact rule list in `cross_artifact.py` if Tier 2 rules changed.
4. Update the fixture suite: add good/bad cases for new or changed rules.
5. Append an entry to `AMENDMENTS.md` naming the old version, the new version, and the change.
6. Run the validator's own self-test (contract-set consistency check) and the full pytest suite.

SC-007 caps the effort at under one working day of focused effort and requires that no pipeline / evaluator business logic is touched.

**Rationale**: The written path must have exactly one authoritative location or contributors will follow whichever version they read last. Placing the checklist inside the machine layer (next to `v{X.Y.Z}/`) keeps it discoverable when you are already editing schemas; the constitution already governs *that* amendments happen, so it needs no duplication.

**Alternatives considered**:
- **Amendment path inside `docs/stage1-vendor-identity/`**: rejected. That directory is the human layer; the amendment path is cross-cutting and should live next to the machine layer where most of the edits land.
- **Inside each version directory's `README.md`**: rejected. Duplicates the checklist across versions; hard to change the process itself.

---

## R7. Corpus folder scaffolding vs. labeling

**Decision**: This feature creates the corpus root (`tests/stage1_vendor_identity/`) as an empty scaffold with a `.gitkeep` and a `README.md` pointing at `docs/stage1-vendor-identity/dataset-layout.md`. It does **not** create 20 per-document folders or any `expected.json` files. Actual labeling is an orthogonal workstream.

**Rationale**: The folder contract (FR-028 through FR-032) needs the corpus-root path to exist for the validator's `validate corpus` subcommand to be runnable, but creating empty per-document folders would produce validator failures with no useful content (missing `source.pdf`, missing `expected.json`). Labeling is Workstream A from the test-harness PRD and proceeds in parallel with this feature.

**Alternatives considered**:
- **Create 20 empty per-document folders**: rejected. Produces noise and forces every `validate corpus` run to fail until labeling catches up.
- **Bundle sample labeled documents with the feature**: rejected. Labeling needs real PDFs, which are not part of this slice.

---

## R8. Python packaging for this slice

**Decision**: Add a minimal `pyproject.toml` at repo root declaring the `dartwing_ocr` package under `src/`, plus `jsonschema`, `pydantic`, and `pytest` as dependencies. Keep `requirements.txt` for backward compatibility with the existing prototype script (`step2_ocr_ensemble.py`), but the validator's install path is `pip install -e .` inside the devcontainer.

**Rationale**: The implementation plan calls for the repo to become a Python module, not just a loose script. Starting `pyproject.toml` now avoids a bigger restructure later. The validator has narrow dependencies and does not pull in PaddleOCR/PyTorch.

**Alternatives considered**:
- **Stay on `requirements.txt` only, run tests via `PYTHONPATH=src pytest`**: rejected. Works, but delays the inevitable packaging step and makes later modules (preprocess/, extract/, routing/) harder to install cleanly.

---

## Resolved NEEDS CLARIFICATION markers

None remain. The spec-level Clarifications session resolved the five user-facing ambiguities; this document resolves the six implementation-layer decisions introduced by the Technical Context, plus two operational decisions (R7, R8). Phase 1 can proceed.
