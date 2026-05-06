# Implementation Plan: Workstation Paddle GPU Preprocessing Validation

**Branch**: `014-paddle-gpu-preprocessing` | **Date**: 2026-05-06 | **Spec**: [`spec.md`](./spec.md)
**Input**: Feature specification from `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/014-paddle-gpu-preprocessing/specs/014-paddle-gpu-preprocessing/spec.md`

## Summary

Add a disciplined GPU validation path for stage 1 preprocessing without
disturbing the CPU default. Deliver three slices in priority order:

1. **P1 — GPU readiness preflight.** A single discoverable command
   (`python -m ledgerlinc_ocr.preprocessing.preflight`) that classifies the
   environment into one of the six FR-001 states and emits a dual readout:
   human-readable text on stdout followed by exactly one trailing JSON line
   (`kind: "preflight_readout"`) carrying the FR-002 evidence. The same
   classifier code is consumed inline by the pipeline's GPU gate.
2. **P2 — Opt-in `ppstructurev3@gpu` preprocessing profile.** Extend the
   closed profile vocabulary, plumb the lane through the preprocessing
   engine factory (selecting `device="gpu:0"` instead of `"cpu"`), and
   encode profile + device in `pipeline_version` (e.g.
   `…+paddleocr3.5.0.0000000.dpi300.gpu0`). Fail-fast on missing GPU
   prerequisites by invoking the shared classifier inline before the first
   artifact write. Multi-document harness runs abort on the first GPU
   inference failure regardless of `--on-failure` mode.
3. **P3 — CPU-vs-GPU timing evidence.** Add additive
   `profile_initialization_seconds` lane breakdown and per-document GPU
   stage timings to the existing feature-011 `kind: "run_summary"` stdout
   JSON line. No new persisted artifact, no schema change.

The CPU profile remains the default and byte-stable; no stage 1 schema
changes; no committed-baseline regeneration; no Jetson lane.

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` and existing `pyproject.toml` `requires-python = ">=3.12"`).
**Primary Dependencies**: existing — `paddleocr>=3.5,<4`, `paddlex[ocr]>=3.5,<4`, `paddlepaddle>=3.0,<4` (CPU baseline; the optional GPU wheel `paddlepaddle-gpu` is an out-of-tree workstation install — see research R-014.7), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`. No new pinned dependency added by this feature; the GPU wheel is documented as an additive optional install path per FR-024.
**Storage**: Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`; writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. Preflight writes nothing to disk per FR-004. No DB.
**Testing**: pytest 8.x via `[project.optional-dependencies] dev`; `pytest-socket` for network isolation; new `gpu` pytest marker for FR-019 skip-gating tied to the shared preflight classifier (research R-014.9).
**Target Platform**: Linux (devcontainer + native ROCm host). WSL Docker Desktop is explicitly *not* a supported GPU runtime; the preflight readout will diagnose that case.
**Project Type**: CLI / library (single project layout, matches features 010/011).
**Performance Goals**: SC-001 — preflight returns within five minutes wall-clock from cold weights cache. SC-008 — warm GPU per-document preprocessing time measurably lower than warm CPU on the same invoice. No hard latency target (constitution Stage 1 Scope Constraints).
**Constraints**: FR-015/FR-025 — no schema field added/removed/repurposed; no canonical artifact filename change; no `edge-ocr@jetson` profile; no remote cloud execution; CPU profile must remain byte-stable (FR-017).
**Scale/Scope**: ≤20 invoices in the labeled corpus today (`tests/stage1_vendor_identity/`); a GPU run targets the same per-document folder layout; one new module (`preflight.py`), one extended CLI script, ~12 new functional requirements covered.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Gate | Compliance |
|---|---|
| **I. One Repo, Clear Runtime Boundaries** | The pipeline retains preprocessing/extraction/routing/assembly ownership; the harness retains corpus/evaluation. The feature does *not* embed a model runtime into the pipeline container — the GPU profile runs PaddleOCR via the existing in-process Python import, just like the CPU profile, on whatever Paddle wheel the operator installs (CPU or GPU). The optional `paddlepaddle-gpu` wheel is a workstation/native-ROCm install path documented as additive (FR-024). |
| **II. Evidence-First, Schema-First Design** | No stage 1 schema field added, removed, or repurposed (FR-015, FR-025). The `preprocess_output.json` shape under `contract_set_version` 1.2.0 stays frozen. The only carrier for profile/device identity is the free-form `pipeline_version` string (Clarification Q1). |
| **III. Deterministic Control Over Model Output** | Spam gates, consensus, routing, and review remain deterministic code. The new GPU classifier is also deterministic — given the same environment it produces the same FR-001 state. |
| **IV. Provenance and Review Safety** | No change. Vendor identity provenance fields are untouched. |
| **V. Benchmarkable and Reproducible Delivery** | One-document end-to-end execution still works on CPU. The GPU profile adds a *third* lane comparable through `pipeline_version` parsing. CPU baseline byte-stability is preserved (FR-017, SC-006). |
| **Quality Gate 1** (pipeline/harness boundaries) | Boundaries unchanged; no PRD swap. |
| **Quality Gate 2** (output contracts) | No schema change. `docs/stage1-vendor-identity/schemas.md` is read-only for this feature. |
| **Quality Gate 3** (runtime behavior) | The Paddle GPU runtime path on AMD/ROCm WSL is *unproven*. The feature treats that uncertainty as the deliverable: preflight is the documented runtime check. `docs/stage1-vendor-identity/ollama-runtime.md` and a new `docs/stage1-vendor-identity/paddle-gpu-preflight.md` describe the supported path once preflight outcomes pin it. |
| **Quality Gate 4** (verifiable local execution) | The GPU integration test (FR-020) provides one concrete local execution path. The CPU integration test from feature 010 still runs unchanged. |
| **Quality Gate 5** (container vs. native distinction) | Preflight reports container/runtime device exposure as an explicit FR-001 sub-state and never represents WSL Docker GPU success as production-ready. |
| **Quality Gate 6** (evaluation comparison) | No change to evaluator or `expected.json` truth. |
| **Quality Gate 7** (architecture consistency) | This feature realizes the trijunction-ingestion `PaddleOCR-VL-1.5` lane on workstation GPU — a step toward the target architecture, not a deviation from it. No declared deviation needed. |

**Result: PASS.** No violations require Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/014-paddle-gpu-preprocessing/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # /speckit.specify + /speckit.clarify output (already exists)
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/
│   └── cli-contract.md  # Phase 1 — preflight CLI + extended pipeline CLI surface
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/ledgerlinc_ocr/
├── preprocessing/
│   ├── cli.py                        # extended — accept ppstructurev3@gpu via --preprocess-profile resolution
│   ├── ocr.py                        # extended — _get_engine() takes a lane and selects device="cpu" | "gpu:0"
│   ├── pipeline.py                   # extended — invokes shared preflight classifier when lane=="gpu"
│   ├── version.py                    # extended — build_pipeline_version() takes a `lane`/`device` segment (e.g. ".cpu" | ".gpu0")
│   ├── preflight.py                  # NEW — shared classifier + dataclasses for FR-001 states; pure library
│   ├── preflight_cli.py              # NEW — `python -m ledgerlinc_ocr.preprocessing.preflight` CLI; emits dual readout
│   └── …                             # unchanged: rasterize.py, document_text.py, etc.
└── pipeline/
    ├── profiles.py                   # extended — add ("preprocess", "ppstructurev3", "gpu") to SUPPORTED_PROFILES
    ├── runner.py                     # extended — preflight gate before first preprocess invocation; abort-on-first-GPU-failure logic
    ├── timing.py                     # extended — RunSummary gains optional preprocess GPU timing fields (additive)
    └── …                             # unchanged

tests/
├── unit/
│   ├── test_preflight_classifier.py          # NEW — table-driven FR-001 state classification (mocked Paddle)
│   ├── test_preflight_cli_dual_format.py     # NEW — text + trailing-JSON-line formatter test
│   └── test_pipeline_version_lane_segment.py # NEW — version string parsing/round-trip
├── integration/
│   ├── test_pipeline_gpu_gate_failfast.py    # NEW — selecting ppstructurev3@gpu without GPU fails before artifact write
│   ├── test_pipeline_gpu_e2e.py              # NEW — gpu-marked; FR-020; skipped if preflight non-pass
│   └── test_runsummary_gpu_timing_fields.py  # NEW — gpu-marked; verifies additive timing fields
├── pipeline_tests/
│   ├── test_profiles_vocabulary.py           # extended — accepts ppstructurev3@gpu; rejects stub@gpu
│   └── test_pipeline_version_cpu_byte_stable.py # NEW — SC-006 byte-stability regression guard
└── conftest.py                       # extended — register `gpu` marker, hook FR-019 skip rationale to preflight states

docs/stage1-vendor-identity/
└── paddle-gpu-preflight.md           # NEW — runs through each FR-001 state, the recommended remediation, and the supported install path
```

**Structure Decision**: Single-project layout, identical to features 010 and
011. The new module is a single library file (`preflight.py`) plus a thin
CLI wrapper (`preflight_cli.py`) so both the standalone preflight command
and the pipeline's runtime gate import the same classifier. This satisfies
the Q2 clarification (shared checker, single source of truth for the
FR-001 vocabulary) and keeps the in-tree placement promised in the spec
Assumptions.

## Phase 0 Outline

Research items in `research.md`, all keyed `R-014.x`. Each resolves either
a NEEDS CLARIFICATION from Technical Context above or a non-trivial
implementation decision flagged by the spec.

- **R-014.1** Preflight CLI placement — `python -m ledgerlinc_ocr.preprocessing.preflight` vs. a top-level entrypoint vs. a subcommand of `ledgerlinc-preprocess`. Decision recorded with reasoning grounded in FR-006 ("single documented command") and the existing module CLI pattern (`python -m ledgerlinc_ocr.validator`).
- **R-014.2** `pipeline_version` lane segment grammar — what string segment encodes profile + device for SC-005. Locks the format (e.g. trailing `.cpu` / `.gpu0`) so downstream consumers can parse it deterministically without breaking SC-006 byte-stability for the CPU lane.
- **R-014.3** Shared classifier API surface — function signature, returned dataclass, FR-001 state enum, and the boundary between "I observed this" and "I recommend that". Defines what both the CLI and the pipeline gate import.
- **R-014.4** Reconciling Q3 abort-on-first-GPU-failure with the existing feature-011 `--on-failure` flag default of `continue` in warm-corpus mode. Decides whether GPU lane forces fail-fast unconditionally, or whether `--on-failure=continue` is rejected at parse time when preprocess is `ppstructurev3@gpu`.
- **R-014.5** Preflight dual readout — exact text section layout, JSON object schema (`kind: "preflight_readout"`), and exit-code mapping per FR-001 state.
- **R-014.6** `run_summary` extension fields — names, types, and additive contract guarantee for the new preprocess GPU timing keys (Q5).
- **R-014.7** Paddle GPU detection mechanics — which Paddle 3.x APIs to call (`paddle.is_compiled_with_cuda`, `paddle.is_compiled_with_rocm`, `paddle.device.is_compiled_with_*`, `paddle.device.cuda.device_count`), how to distinguish "CPU-only build" from "GPU build, no device", and how to obtain the Paddle build flag string for the readout. Resolved via `mcp__plugin_context7_context7__query-docs` against the active PaddlePaddle/PaddleOCR docs.
- **R-014.8** PPStructureV3 device-string vocabulary — what `device=` accepts in PaddleOCR 3.5 (`"cpu"`, `"gpu"`, `"gpu:0"`, ROCm-specific?), and how the GPU init exception surfaces when the wheel is CPU-only.
- **R-014.9** Pytest marker + skip mechanism — `gpu` marker registration, conftest hook that calls the shared classifier once per session, skip-reason wording mapped to FR-001 states for FR-019.
- **R-014.10** Runtime device exposure detection — heuristics for "GPU device not exposed to runtime" (presence of `/dev/dri`, `/dev/kfd`, `HIP_VISIBLE_DEVICES`, container vs. host signals) without making the classifier fragile.
- **R-014.11** Documenting workstation-only GPU install path additively — `docs/stage1-vendor-identity/paddle-gpu-preflight.md` outline; pin which wheel(s) to point at without introducing them to `requirements.txt` / `pyproject.toml` (FR-024).

**Output**: `research.md` covering R-014.1 through R-014.11, with all
decisions, rationale, and rejected alternatives, including any docs
fetched via `mcp__plugin_context7_context7__query-docs`.

## Phase 1 Design

Prerequisites: `research.md` complete.

1. **Entities → `data-model.md`**:
   - `PreflightState` (enum) — the six FR-001 states.
   - `PreflightEvidence` (frozen dataclass) — interpreter, env path, Paddle/PaddleOCR versions, build flags, device count, selected device, runtime device exposure, PPStructureV3 init result + duration.
   - `PreflightReadout` (frozen dataclass) — `state: PreflightState`, `evidence: PreflightEvidence`, `recommendation: str`, plus `to_text()` and `to_json_dict()` serializers.
   - `LaneSegment` (string-typed value object) — the parseable `.cpu` / `.gpu<N>` suffix appended to `pipeline_version`.
   - `RunSummary` (existing, additive) — gains `preprocess_initialization_seconds_by_lane` (or analogous additive key) and `per_document.stages.preprocess.gpu_*_seconds` phase keys per R-014.6.

2. **Interface contracts → `contracts/cli-contract.md`**:
   - `python -m ledgerlinc_ocr.preprocessing.preflight` — exit codes, stdout shape (text section + trailing JSON line), stderr usage, exit-code-to-state table, no-disk-write guarantee.
   - `ledgerlinc-preprocess … --preprocess-profile ppstructurev3@gpu` — CLI surface unchanged (the flag already exists from feature 011); contract additions are: (a) the new value is accepted, (b) the value is rejected with a named missing-prerequisite error before any artifact write when preflight does not pass, (c) the produced `preprocess_output.json` carries the lane segment in `pipeline_version`.
   - `ledgerlinc-pipeline …` (warm-corpus / single-doc) — additive: when preprocess profile is the GPU lane, the harness aborts on first GPU inference failure regardless of `--on-failure`, and the `run_summary` JSON line carries the additive timing fields from R-014.6.

3. **`quickstart.md`** — a developer walkthrough:
   - Install/verify the GPU wheel (workstation-only, additive).
   - Run preflight; read each FR-001 state and its remediation.
   - Run a single-document preprocessing pass with `--preprocess-profile ppstructurev3@gpu`.
   - Compare warm CPU vs. warm GPU timing via tee-ed `run_summary` JSON.
   - Confirm CPU run remains byte-stable.

4. **Agent context update** — Run
   `.specify/scripts/bash/update-agent-context.sh claude` to add this
   feature's Active Technology bullets and Recent Changes line to
   `CLAUDE.md`.

**Output**: `data-model.md`, `contracts/cli-contract.md`, `quickstart.md`,
agent-context update.

### Post-Design Constitution Re-Check

Re-evaluated after Phase 1 below; same gates apply.

- All four stage 1 artifact schemas remain untouched (Gate 2). ✓
- `pipeline_version` is the only artifact-side carrier of new identity, and it is a free-form string today (Clarification Q1). ✓
- The shared classifier module is the single source of truth for FR-001 vocabulary; the pipeline gate cannot diverge (Clarification Q2). ✓
- Multi-document GPU failure aborts the whole run; this is a tightened policy on top of the existing feature-011 `--on-failure` surface, not a new flag (Clarification Q3, R-014.4). ✓
- Preflight dual format (text + trailing JSON) reuses the run-summary stdout convention, no new contract style (Clarification Q4, R-014.5). ✓
- Timing surfaces as additive fields on the existing `run_summary` JSON; no new artifact (Clarification Q5, R-014.6). ✓
- No GPU dependency added to `requirements.txt` / `pyproject.toml` runtime extras (FR-024); GPU wheel is documented as workstation-only. ✓

**Result: PASS post-design.** No new Complexity Tracking entries.

## Complexity Tracking

> Filled only when Constitution Check has unjustified violations.

*None — Constitution Check passed in both pre-Phase-0 and post-Phase-1
evaluations.*

## Milestones

Aligned to the user-story priorities in `spec.md`:

- **M1 — Preflight library + CLI (P1).** Land `preflight.py`,
  `preflight_cli.py`, the dual-format readout, the `gpu` pytest marker,
  and `docs/stage1-vendor-identity/paddle-gpu-preflight.md`. Independent
  test: per US1 acceptance scenarios 1–6.
- **M2 — `ppstructurev3@gpu` profile in pipeline (P2).** Extend
  `profiles.py`, `ocr.py`, `version.py`, `pipeline.py`, and `runner.py`.
  Wire the shared classifier into the GPU runtime gate. Add the GPU
  integration test (FR-020). Independent test: per US2 acceptance
  scenarios 1–6.
- **M3 — Timing evidence in `run_summary` (P3).** Add additive timing
  fields to `RunSummary`, populate them from the warm-corpus runner, and
  add `tests/integration/test_runsummary_gpu_timing_fields.py`.
  Independent test: per US3 acceptance scenarios 1–4.

Each milestone ships its own tests and docs and is independently
shippable per the spec's "Independent Test" gates. M2 and M3 are gated on
M1; M3 is gated on M2.
