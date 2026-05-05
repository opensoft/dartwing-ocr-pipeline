# Implementation Plan: Stage Runtime Profiles / Root Master Controller

**Branch**: `011-stage-runtime-profiles` | **Date**: 2026-05-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-stage-runtime-profiles/spec.md`

## Summary

Stand up the stage 1 root/master controller as a thin orchestration layer over the existing per-stage modules (`preprocessing/`, `extract/`, `router/`, `assembler/`). The controller adds five capabilities to the existing `python -m ledgerlinc_ocr.pipeline run` entrypoint without changing any of the four canonical artifact contracts:

1. **Per-stage profile flags** (`--preprocess-profile`, `--extract-profile`, `--routing-profile`, `--final-payload-profile`) plus a `--stack-preset` convenience expansion (`full-workstation`, `cloud-workstation`, `edge-fast`).
2. **Execution slicing** (`--start-at` / `--stop-after`) with prerequisite-artifact validation against the installed contract set and overwrite scoping limited to the selected slice.
3. **Stub-seam preservation** - the existing injected-callable seam and explicit `stub` profiles remain first-class so contract/unit tests stay deterministic and network-free.
4. **Warm corpus mode** invoked via `--documents-file <path>` (one per-document folder per line, mutually exclusive with `--document-folder`). The selected live preprocessing profile is initialized exactly once per process and reused across all listed documents. Default failure policy is continue-through-failures; opt into fail-fast via `--on-failure fail-fast`.
5. **Run timing summary** emitted as a single end-of-run JSON object on stdout (after all per-document records) carrying `kind: "run_summary"` so the harness can distinguish it from per-document success/failure records. Per-document records keep the existing `002-cli-contract` shape.

Implementation is sequenced per FR-034: thin foundation first; warm `ppstructurev3@cpu` corpus path second; real default profile wiring third; secondary lanes (`ollama@cpu`, `ollama@jetson`, `edge-ocr@jetson`, `ensemble@workstation`, `cloud-workstation`, `edge-fast`) fourth. `ensemble@workstation` endpoint configuration is deferred to the secondary-lane slice per FR-022A; this feature only requires that profile validation recognize it and fail fast with a named missing-endpoint error when it is selected without configured endpoints.

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` base image and existing `ledgerlinc-ocr` package pinned in `pyproject.toml`).

**Primary Dependencies**: No new third-party dependencies. Reuses already-declared packages:
- `jsonschema>=4.22,<5` (prerequisite-artifact validation via the existing `ledgerlinc_ocr.validator` module).
- `pydantic>=2.7,<3` (typed in-process result objects for run summary, per-document records, profile resolution).
- `httpx>=0.27,<1` (existing Ollama HTTP client; CPU/Jetson lanes reuse it).
- `PyYAML>=6.0,<7` (already pulled in for voter configs; not added here, but available if a future ensemble-config file needs it).
- Python stdlib (`argparse`, `json`, `pathlib`, `dataclasses`, `time.monotonic_ns`, `os`).

**Storage**: Filesystem only. Reads:
- `--documents-file <path>` - UTF-8 text file, one per-document folder path per line, blank lines and `#`-prefixed comments ignored.
- Per-document `<folder>/preprocess_output.json` / `edge_extraction_output.json` / `routing_decision.json` as prerequisite artifacts when the slice starts after preprocess.

Writes:
- Exactly the four canonical artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) into each per-document folder, scoped to the selected slice.
- Stdout: per-document success records (existing `002-cli-contract` shape) plus one end-of-run `kind: "run_summary"` JSON object in warm-corpus mode.

No database. No new persisted on-disk artifact. No remote cloud calls.

**Testing**: `pytest` with the existing test layout (`tests/contract_tests/`, `tests/pipeline_tests/`, `tests/unit/`, `tests/integration/`) and `pytest-socket` for network-free contract assertions. Coverage targets:
- New `tests/pipeline_tests/test_profile_resolver.py` and `test_slice_control.py` for foundation.
- New `tests/integration/test_warm_corpus_documents_file.py` for warm-corpus orchestration with stub profiles (no Ollama required) and one real `ppstructurev3@cpu` test gated by Paddle availability.
- Extend existing `tests/contract_tests/test_cli_contract.py` to cover the amended `002` surface (new flags, mutual exclusions, scope of overwrite guard).

**Target Platform**: Linux (devcontainer + native Linux ROCm host for `ollama@gpu`); WSL2 dev path. `cloud-workstation` runs on the same workstation host with multiple local model endpoints. `edge-fast` targets Jetson Nano Super class hardware (implementation deferred to FR-034 step 4).

**Project Type**: Python CLI/library - single project, extending the existing `src/ledgerlinc_ocr/pipeline/` package.

**Performance Goals**:
- SC-009: warm corpus run over N documents with `ppstructurev3@cpu` initializes the PPStructureV3 preprocessing profile **exactly once per process**, not N times. The current cold-per-document path is the baseline this slice must beat without changing artifact filenames or schemas.
- No release-gate latency target per constitution Stage 1 Scope Constraints.

**Constraints**:
- No artifact schema changes (FR-029); contract set version remains pinned by the caller.
- No new persisted benchmark artifact (FR-030, FR-036).
- No remote cloud-provider calls or credential handling (FR-021, FR-036).
- No second repository for the edge OCR scanner (FR-036).
- Per-document folder still holds exactly one canonical set of the four artifacts for one selected run (FR-036).
- `--documents-file` and `--document-folder` and `--input` are mutually exclusive (FR-023).
- Lane changes (e.g., `ollama@gpu` -> `ollama@cpu`) MUST NOT change artifact filenames or schemas (FR-014).
- Validation MUST fail before any artifact write on unsupported profile/lane combinations (FR-008) and on missing prerequisites (FR-010).

**Scale/Scope**:
- Stage 1 corpus is 20 per-document folders under `tests/stage1_vendor_identity/inv_XXX_<difficulty>/` (per spec 006).
- Profile vocabulary is fixed at the values in FR-006; the resolver is closed-set, not extensible at runtime.
- Three explicit Ollama lane URLs (gpu / cpu / jetson) plus deferred `ensemble@workstation` voter set.

## Constitution Check

Reference: `.specify/memory/constitution.md` (v1.3.0).

| Principle / Gate | Verdict | Notes |
|---|---|---|
| I. One Repo, Clear Runtime Boundaries | PASS | FR-033 keeps controller responsibilities scoped to stage-profile resolution, slicing, prerequisite/overwrite checks, lifecycle, and timing metadata; corpus selection, scoring, and reporting remain harness concerns. |
| II. Evidence-First, Schema-First Design | PASS | FR-029 forbids artifact schema changes; existing validator gates remain in force; new run summary is metadata, not an artifact. |
| III. Deterministic Control Over Model Output | PASS | Profile resolver, slice control, prerequisite checks, overwrite scoping, and run summary are all deterministic code. Routing/final-payload remain `@cpu` deterministic stages. |
| IV. Provenance and Review Safety | PASS | Feature does not modify company-name provenance, vendor-identity logic, or `manual_review_required` semantics. |
| V. Benchmarkable and Reproducible Delivery | PASS | One-document path preserved (cold debugging). Warm corpus mode adds a new reproducible path that runs against the labeled corpus and feeds the existing harness/evaluator without changing comparison surface. |
| Stage 1 Scope Constraints | PASS | PDF input only; vendor identity only; no remote cloud; no latency gate; `cloud-workstation` is local-GPU validation only (FR-021). |
| Q-Gate 1 (boundary preservation) | PASS | FR-033 + Assumptions section. |
| Q-Gate 2 (output contracts) | PASS | No `docs/stage1-vendor-identity/schemas.md` change required (FR-029). |
| Q-Gate 3 (runtime/architecture docs) | TASK | Plan adds documentation-update tasks for `docs/stage1-vendor-identity/architecture.md` and `docs/stage1-vendor-identity/ollama-runtime.md` to describe the controller layer, the `--documents-file` warm-corpus path, and the CPU/Jetson Ollama lane env vars. Tracked under Phase 1 deliverables. |
| Q-Gate 4 (verifiable local execution) | PASS | quickstart.md (Phase 1) walks through stub-only and warm `ppstructurev3@cpu` execution paths in the devcontainer. |
| Q-Gate 5 (runtime/container changes) | PASS | No new containers introduced. WSL vs. native Linux ROCm distinction is preserved by reusing existing `--ollama-url` resolution; new CPU/Jetson lanes are explicit. |
| Q-Gate 6 (evaluation comparison) | PASS | Evaluator inputs unchanged. Run summary is additive on stdout. |
| Q-Gate 7 (Speckit consistency with `architecture.md`) | PASS | Spec restates the controller scope from `architecture.md`'s Trijunction + ensemble target. No declared deviation. |

**Constitution Check verdict**: PASS - no violations. Documentation tasks for Q-Gate 3 are normal deliverables, not gate failures. **Complexity Tracking** section is therefore not required.

## Project Structure

### Documentation (this feature)

```text
specs/011-stage-runtime-profiles/
+-- plan.md                         # This file (/speckit.plan)
+-- spec.md                         # /speckit.specify + /speckit.clarify output
+-- research.md                     # Phase 0 output (this command)
+-- data-model.md                   # Phase 1 output (this command)
+-- quickstart.md                   # Phase 1 output (this command)
+-- contracts/
|   +-- cli-contract.md             # Phase 1 output: amended 002-cli-contract surface
+-- tasks.md                        # /speckit.tasks output (NOT created by this command)
```

### Source Code (repository root)

```text
src/ledgerlinc_ocr/pipeline/
+-- __init__.py                     # existing
+-- __main__.py                     # existing - preserved
+-- cli.py                          # AMEND: add --*-profile, --stack-preset,
|                                   #        --start-at, --stop-after,
|                                   #        --documents-file, --on-failure,
|                                   #        --ollama-cpu-url, --ollama-jetson-url
+-- exit_codes.py                   # existing - extend ExitCode enum if needed
+-- path_resolution.py              # existing - extend for documents-file path resolution
+-- pdf_check.py                    # existing - preserved
+-- runner.py                       # AMEND: parameterize stage callables by resolved
|                                   #        profile; respect slice; scoped overwrite
+-- stages.py                       # AMEND: keep stub callables; add profile->adapter
|                                   #        registry that imports the existing
|                                   #        preprocessing/extract/router/assembler modules
+-- profiles.py                     # NEW - closed-set profile vocabulary, parsing,
|                                   #        validation, stack-preset expansion
+-- slice_control.py                # NEW - --start-at / --stop-after parsing,
|                                   #        prerequisite-artifact validation against
|                                   #        the installed contract set
+-- corpus.py                       # NEW - --documents-file parsing, warm-corpus
|                                   #        orchestration, per-doc record emission
+-- timing.py                       # NEW - per-document/per-stage timing capture and
|                                   #        kind:"run_summary" stdout emitter
+-- ollama_lanes.py                 # NEW - gpu/cpu/jetson URL resolution + env vars
+-- failure_policy.py               # NEW - --on-failure parsing, default continue-
                                    #        through-failures, fail-fast opt-in

# Reused without modification (profile->adapter targets):
src/ledgerlinc_ocr/preprocessing/   # ppstructurev3@cpu adapter target
src/ledgerlinc_ocr/extract/         # ollama@gpu (existing); ollama@cpu / @jetson
                                    # routed via the same module with different URLs
src/ledgerlinc_ocr/router/          # rules@cpu adapter target
src/ledgerlinc_ocr/assembler/       # assembler@cpu adapter target
src/ledgerlinc_ocr/validator/       # prerequisite-artifact validation reuse

tests/
+-- contract_tests/
|   +-- test_cli_contract_011_amendment.py          # NEW - covers amended surface
+-- pipeline_tests/
|   +-- test_profile_resolver.py                    # NEW
|   +-- test_slice_control.py                       # NEW
|   +-- test_overwrite_scoping.py                   # NEW
|   +-- test_failure_policy.py                      # NEW
|   +-- test_ollama_lanes.py                        # NEW
|   +-- test_run_summary_emission.py                # NEW
+-- integration/
|   +-- test_warm_corpus_stub_profiles.py           # NEW - Paddle-free
|   +-- test_warm_corpus_ppstructurev3_cpu.py       # NEW - gated on Paddle availability
+-- unit/                                           # extend existing modules' unit tests
```

**Structure Decision**: Single-project Python package layout, extending the existing `src/ledgerlinc_ocr/pipeline/` orchestration package. New code is split into small focused modules (`profiles.py`, `slice_control.py`, `corpus.py`, `timing.py`, `ollama_lanes.py`, `failure_policy.py`) so each FR cluster maps cleanly to one module and one test file. The existing per-stage packages (`preprocessing`, `extract`, `router`, `assembler`) are **reused unchanged** as profile adapter targets - feature 011 is an orchestration layer, not a re-implementation of any stage.

## Complexity Tracking

> Not applicable - Constitution Check passed with no violations. No deviations from the constitution or `architecture.md` to justify.
