# Implementation Plan: GPU MVP Demo Hardening

**Branch**: `023-gpu-mvp-demo-hardening` | **Date**: 2026-05-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/023-gpu-mvp-demo-hardening/spec.md`

## Summary

Land `python -m dartwing_ocr.gpu_demo` (optionally `dartwing-gpu-demo`) as the single supported entry point for the workstation MVP GPU smoke/demo. The CLI composes existing pipeline sub-modules — feature 014 Paddle ROCm preflight + feature 018 `header-first-v1` preprocessing → feature 005 single-voter extraction → feature 008 routing → feature 009 final-payload assembly — behind:

- A **fixed-order readiness preflight** of 8 named checks (FR-016) with a 10-second wall-clock bound (SC-007).
- A **600-second bounded pipeline timeout** (FR-008) with named `stalled_phase` capture on expiry.
- An **always-emit `DemoRunReport`** as a single UTF-8 newline-terminated JSON line on stdout (FR-019, SC-009), with the same top-level key set on every outcome (success / readiness-fail / runtime-fail / timeout / `--check-only` / invalid-input).
- A **deterministic eager-delete** of only the four canonical artifacts (FR-017, SC-010) inside a canonicalized per-document folder, with hard guards against symlink-escape and partial-delete failure.
- A **CPU-isolated pytest coverage** (SC-008) using stubbed Paddle ROCm preflight + stubbed host Ollama, plus a workstation-only manual GPU smoke gate documented in the runbook.

No new schemas. No new persisted artifact. No contract-set bump (FR-014). No Jetson behavior (FR-013).

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`).

**Primary Dependencies**: Existing only — no new pinned dependency. The demo composes:
- `httpx>=0.27,<1` (already declared by feature 005) for Ollama HTTP probes.
- `paddleocr>=3.5,<4` + `paddlepaddle-dcu` (workstation-only optional install) for the feature 014 Paddle ROCm preflight call.
- `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3` indirectly via feature 014/018 preprocessing.
- `jsonschema>=4.22,<5`, `pydantic>=2.7,<3` for re-using the existing validator and report dataclasses.
- Python stdlib: `argparse`, `json`, `pathlib`, `dataclasses`, `os`, `signal`, `subprocess`-or-direct-import (composition mechanism is a planning decision below), `time`, `unicodedata`.

**Storage**: Filesystem only. Reads `<document-folder>/source.pdf` (default `tests/stage1_vendor_identity/inv_001_easy/source.pdf`); writes the four canonical artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) into the same folder. No new persisted artifact (FR-019). Voter-config YAML is read from `--voter-config <path>` or feature 005/021 auto-discovery.

**Testing**: `pytest>=8` (already declared). CPU-isolated tests stub the Paddle ROCm preflight and host Ollama HTTP (the stubs satisfy the same contract the venv-resident preflight would, per SC-008 expanded clause). Workstation-only manual smoke runs the real `header-first-v1` GPU path against `tests/stage1_vendor_identity/inv_001_easy/` and records evidence in the runbook (SC-006 three-run stability gate).

**Target Platform**: Workstation WSL2 (`gfx1151` AMD GPU exposed via ROCm) running host Ollama at `OLLAMA_BASE_URL` (default `http://localhost:11434`) and the `.venv-paddle-rocm` Python environment for operator runs. CI runs on Linux without ROCm using stubs only.

**Project Type**: Single-project (Python package + CLI). The new module is a sibling of `dartwing_ocr.extract`, `dartwing_ocr.router`, and `dartwing_ocr.assembler`.

**Performance Goals**:
- Readiness preflight (`--check-only`): ≤ 10 s wall-clock on a warm workstation (SC-007).
- Full pipeline (cold or warm): ≤ 600 s wall-clock (FR-008).
- Three-run stability: identical readiness verdict + identical `runtime_outcome` + identical `quality_status` across three consecutive runs on the canonical fixture (SC-006).

**Constraints**:
- Stable top-level JSON shape on stdout across every outcome (FR-019); `null` never omitted.
- Closed exit-code table 0–5 (FR-021), closed `runtime_outcome` enum (FR-020), closed `quality_status` enum (FR-010), closed readiness vocabulary (FR-016).
- Eager-delete operates on exact basenames in a canonicalized per-document folder; symlink-escape and any delete failure abort with exit 2 (FR-017, triage C2/C6).
- No CPU fallback masquerading as success (FR-012); enforced by readiness + post-run device interrogation.
- No new contract set version (FR-014).

**Scale/Scope**:
- Single canonical fixture: `tests/stage1_vendor_identity/inv_001_easy/` (FR-027 default).
- Single workstation, single operator, single GPU device.
- No multi-document corpus benchmarking in this feature's scope (Out of Scope).

## Constitution Check

*GATE: passes before Phase 0 research; re-evaluated post-Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| **I. One Repo, Clear Runtime Boundaries** | The demo CLI is pipeline-side only — composes existing preprocess / extraction / routing / assembly modules without collapsing concerns; harness, evaluator, and corpus untouched. Local development uses host Ollama by default (FR-006); workstation manual smoke is documented as a native ROCm path, not a Docker Desktop ROCm path. | **PASS** |
| **II. Evidence-First, Schema-First Design** | The four canonical artifacts are unchanged (FR-009, FR-014). `DemoRunReport` is a stdout JSON line, not a persisted artifact, and is not added to the contract set (`contract_set_version` stays at v1.3.0). | **PASS** |
| **III. Deterministic Control Over Model Output** | Readiness checks (FR-016 fixed-order vocabulary), exit codes (FR-021 closed table), `runtime_outcome` (FR-020 closed enum), `quality_status` derivation (FR-010 from evidence-gate + `manual_review_required`), and CPU-fallback detection (FR-012 readiness + post-run interrogation) are all deterministic code. Confidence is consumed as a signal, not as policy. | **PASS** |
| **IV. Provenance and Review Safety** | This feature consumes `manual_review_required` via the `quality_status` mapping; it does not change provenance semantics. Inferred vs explicit company-name handling is unchanged. | **PASS** |
| **V. Benchmarkable and Reproducible Delivery** | US1 + SC-006 deliver one-document end-to-end execution with three-run stability on the canonical fixture; the corpus path remains available via feature 022 / feature 007 evaluator. The demo composes the host-Ollama-with-ROCm-GPU lane. | **PASS** |

**Quality Gates** (from constitution §Quality Gates):

1. ✅ Pipeline / harness boundary preserved — demo CLI is pipeline-side; harness untouched.
2. ✅ Output contracts preserved — no `schemas.md` change required (FR-014); `DemoRunReport` is not on the contract set.
3. ✅ Runtime behavior — extends `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (Q15 round 1) and references `ollama-runtime.md` for the host vs container WSL distinction.
4. ✅ Verifiable local execution — `--check-only` path + full pipeline path on canonical fixture are both documented and tested.
5. ✅ Runtime/container change — host Ollama startup script remains canonical (FR-006); WSL Docker Desktop ROCm path is explicitly out of scope (Out of Scope §).
6. ✅ Evaluation preservation — evaluator is optional via `--with-evaluator` (FR-022); default path does not regress evaluator outputs.
7. ✅ Speckit/architecture consistency — single-voter extraction lineage is consistent with `architecture.md` stage 1 narrowing; no deviation declared needed.

**Result:** Constitution check passes. No violations. **Complexity Tracking section below remains empty.**

## Project Structure

### Documentation (this feature)

```text
specs/023-gpu-mvp-demo-hardening/
├── plan.md                     # this file
├── spec.md                     # mature: 32 clarifications + triage applied
├── research.md                 # Phase 0 output (this command)
├── data-model.md               # Phase 1 output
├── contracts/
│   ├── cli-contract.md         # CLI flags, exit codes, stdout/stderr discipline
│   ├── demo-report-schema.md   # DemoRunReport JSON shape (stable across outcomes)
│   └── readiness-vocabulary.md # fixed 8-check execution order + diagnostic shape
├── quickstart.md               # Phase 1 operator + developer walk-through
├── checklists/                 # 15 release-gate checklists + triage record (pre-existing)
└── tasks.md                    # /speckit.tasks output (NOT created by /speckit.plan)
```

### Source code (repository root)

```text
src/dartwing_ocr/gpu_demo/
├── __init__.py
├── __main__.py                 # `python -m dartwing_ocr.gpu_demo` entry point
├── cli.py                      # argparse: --check-only, --document-folder, --voter-config,
│                               #           --preset, --with-evaluator; flag-interaction guards
├── orchestrator.py             # eager-delete (FR-017), phase invocations, 600 s timeout (FR-008),
│                               # DemoRunReport assembly (FR-019), post-run interrogation (FR-012)
├── readiness/
│   ├── __init__.py
│   ├── base.py                 # ReadinessCheck protocol + result dataclass
│   ├── runner.py               # fixed-order executor; skip-on-upstream-fail (FR-016, FR-026)
│   ├── interpreter.py          # check 1: interpreter/venv (FR-002, FR-003)
│   ├── paddle_preflight.py     # check 2: Paddle ROCm preflight (reuses feature 014)
│   ├── ollama_reach.py         # check 3: Ollama reachability via OLLAMA_BASE_URL
│   ├── ollama_version.py       # check 4: minimum Ollama version (FR-023)
│   ├── ollama_placement.py     # check 5: size_vram > 0 AND size_vram == size (FR-005)
│   ├── ollama_ctx_len.py       # check 6: OLLAMA_CONTEXT_LENGTH from /api/ps (FR-006)
│   ├── schema_validation.py    # check 7: post-pipeline artifact validation (composes validator)
│   └── runtime_timeout.py      # check 8: pipeline runtime bound (composes orchestrator)
├── report.py                   # DemoRunReport, ReadinessSummary, ReadinessCheck, PhaseTimings,
│                               # CPUFallbackDetection, CheckDiagnostic dataclasses (data-model.md §1–§5)
├── serialization.py            # to_json_line() — stable-key UTF-8 single-line emit (R-023.12) +
│                               # round_wall_clock() helper for 3 dp float rounding (R-023.21)
├── enums.py                    # closed Literal types (RuntimeOutcome, StalledPhase, QualityStatus,
│                               # FailureKind, ReadinessCheckName, ReadinessCheckStatus, ProbeResult)
├── exit_codes.py               # closed exit-code table (FR-021)
├── voter_config_loader.py      # --voter-config override + feature 005/021 auto-discovery
├── version.py                  # get_pipeline_version() via importlib.metadata (R-023.2)
├── run_id.py                   # UUID4 run_id + 8-hex-char stderr prefix (R-023.6)
├── log.py                      # INFO/WARN/ERROR stderr severity-prefix helper (R-023.7)
├── folder_canonicalize.py      # canonicalize_document_folder + safe_eager_delete (FR-017)
├── quality_status.py           # derive_quality_status() — R-023.20 truth-table (static)
├── quality_derivation.py       # runtime hook: reads run_summary + final_payload, calls
│                               # quality_status.derive_quality_status; returns (status, source)
├── evaluator_subprocess.py     # --with-evaluator subprocess invocation (R-023.13)
├── cpu_fallback.py             # post-run device interrogation, two probes (R-023.15)
└── diagnostics.py              # format_diagnostic_line() — CheckDiagnostic → stderr text (R-023.11)

tests/integration/gpu_demo/
├── conftest.py                 # Paddle preflight stub, Ollama HTTP stub, fixture-folder builder
├── test_cli_flags.py           # flag parsing, defaults, flag interactions
├── test_readiness_order.py     # fixed-order execution; skip-on-upstream-fail per check
├── test_readiness_failures.py  # each named check class fails in isolation
├── test_exit_codes.py          # 0-5 mapping for every outcome class
├── test_runtime_outcomes.py    # each `runtime_outcome` enum value reached
├── test_check_only.py          # --check-only stable shape, null runtime/quality/timing fields
├── test_report_shape.py        # FR-019 stable top-level key set across all outcomes
├── test_eager_delete.py        # FR-017 path-canonicalization, symlink-escape, partial-failure abort
├── test_with_evaluator.py      # FR-022 warn-and-skip when sidecar missing
└── test_quality_status.py      # FR-010 derivation truth-table

tests/integration/gpu_demo/fixtures/
├── ok/                         # minimal valid fixture
├── missing_source_pdf/         # exit-2 path
├── malformed_voter_config/     # exit-2 path
└── symlink_escape/             # FR-017 guard

docs/stage1-vendor-identity/
└── runbook-gpu-mvp-demo.md     # extended in place per Q15 (round 1 clarification)
```

**Structure Decision:** Single-project layout. The new `gpu_demo` package lives under `src/dartwing_ocr/` alongside existing per-feature modules (`extract/`, `router/`, `assembler/`, `preprocessing/`, `validator/`, `evaluator/`). Tests live under `tests/integration/gpu_demo/` to match the existing layout (feature 005 / 008 / 009 / 020 / 022 lineage). The runbook is extended in `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (created by feature 021) — no new doc file. No SPECKIT START/END markers exist in this project's CLAUDE.md, so the post-plan agent-context update step is N/A here; the plan reference lives in `specs/023-gpu-mvp-demo-hardening/plan.md` and the spec already references it via `## Recent Changes` block (to be updated by `/speckit.tasks`).

## Complexity Tracking

*Empty — no constitution violations to justify.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_ | _(n/a)_ | _(n/a)_ |
