# Implementation Plan: GPU Warmup And MIOpen Cache Stabilization

**Branch**: `016-gpu-warmup-miopen-cache` | **Date**: 2026-05-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-gpu-warmup-miopen-cache/spec.md`

## Summary

Add an explicit, opt-in GPU warmup pass for `ppstructurev3@gpu` that runs exactly once per process between PPStructureV3 engine construction and the first timed document, so MIOpen kernel-selection and COMGR compilation cost is paid up front and reported separately from per-document OCR time. The warmup invocation reuses the engine adopted by feature 015's preflight (`ocr._ENGINE`/`_adopt_engine` — never constructs a second engine), is timed with `time.perf_counter()`, and surfaces as an additive `phase_timings.warmup = {seconds: <float>}` key on the same per-document run_summary entry that feature 015 already attaches `paddle_import` / `gpu_bind_probe` / `engine_init` to (the first successfully processed document). The run_summary `schema_version` bumps codebase-level 0.1.2 → 0.1.3 (per /speckit.clarify Q2: same version for every run of the new binary; the `warmup` key is absent unless warmup actually completed). The feature ships a hybrid MIOpen/COMGR configuration: a default `MIOPEN_FIND_MODE=2` plus a small set of safe env vars enumerated in `research.md` that suppress workspace warnings where possible, with the residual warnings catalogued in the docs deliverable as known runtime diagnostics. Activation surface is a `--gpu-warmup` boolean CLI flag on the existing preprocess CLI (mirroring the orthogonality of `--preprocess-profile`); the same opt-in is also accepted via the `DARTWING_GPU_WARMUP=1` env var for shared-CI ergonomics. Combining the opt-in with `ppstructurev3@cpu` or any stub adapter emits a clear stderr warning (per /speckit.clarify Q1: warn-and-proceed) and otherwise produces a run identical to one without the opt-in. Warmup-pass failures fail-fast with a `warmup failed: <cause>` stderr line and no `phase_timings.warmup` emission (per session 2026-05-07 clarification + FR-007 / SC-011). All feature 015 guarantees (single engine construction per process, no silent CPU fallback, single-device guard, `pipeline_version` ends in `.gpu0`) carry over unchanged. Corpus baselines and `preprocess_output.json` shape are byte-identical to non-warmup runs (FR-018 / SC-008).

## Technical Context

**Language/Version**: Python 3.12 (matches `.devcontainer/Dockerfile` base image and `pyproject.toml requires-python = ">=3.12"`).
**Primary Dependencies**: existing only — `paddleocr>=3.5,<4`, `paddlepaddle-dcu` (workstation-only optional install, already proven in features 014–015), `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`. **No new pinned dependency.** ROCm/MIOpen/COMGR are workstation system dependencies, not Python packages.
**Storage**: filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`. Writes `preprocess_output.json` into the same folder unchanged in shape (FR-018). The warmup pass populates two on-disk OS caches as a side effect — `~/.cache/miopen` and `~/.cache/comgr` — but writes nothing the pipeline owns. Phase timings live exclusively in the existing `kind: "run_summary"` stdout line per feature 015 FR-014; **no new persisted artifact** (FR-019 / SC-002).
**Testing**: pytest. Existing markers `gpu` (deselected without GPU per FR-012) and `live` carry over. New tests under `tests/preprocessing/` and `tests/pipeline/`; existing `tests/contract_tests/` continue to pass unchanged (FR-018). Stub-adapter test suites must continue to pass without GPU (FR-013 / SC-006).
**Target Platform**: Linux (devcontainer + workstation WSL with native ROCm gfx1151 via host Ollama / `.venv-paddle-rocm`). CPU fallback works on any Linux host. Production CI exercises CPU + stub only.
**Project Type**: single Python package (`dartwing-ocr`) with pluggable preprocess profiles. No new top-level subpackage; one new module `preprocessing/warmup.py` plus surgical edits to four existing modules.
**Performance Goals**: no numeric latency target (Constitution: "no latency target as a release gate"; spec Assumptions). Outcomes are observability and variance-reduction — measurable as (a) `phase_timings.warmup.seconds` present on a warmup-enabled run, absent otherwise (SC-001/SC-002); (b) cold-cache `phase_timings.warmup.seconds` ≥ 2× warm-cache value (SC-003, threshold tuneable per /speckit.clarify Q3 and research R-016.3); (c) first-doc `total` / `per_page_inference` exclude warmup duration (SC-004).
**Constraints**:
- FR-001 / FR-004: warmup runs exactly once per process, between engine construction and the first timed document.
- FR-003 / FR-020: warmup MUST reuse the already-constructed PPStructureV3 engine (never instantiate a second engine — preserves feature 015 FR-001 / FR-006).
- FR-007 / SC-011: warmup-pass failure exits non-zero with `warmup failed: <cause>` to stderr and emits no `phase_timings.warmup`; the run MUST NOT silently downgrade to a no-warmup run.
- FR-008: single codebase-level `schema_version` patch bump 0.1.2 → 0.1.3; bumped schema permits `phase_timings.warmup`; key absent unless warmup completed successfully.
- FR-010 / SC-007 (per /speckit.clarify Q1): CPU/stub + `--gpu-warmup` is warn-and-proceed; stderr warning + identical no-opt-in run.
- FR-016 (per /speckit.clarify Q3): hybrid workspace-warning policy — default config suppresses what it safely can; residual warnings catalogued in docs.
- FR-018 / SC-008: `preprocess_output.json` byte-identical to non-warmup runs.
- Constitution I: keep pipeline / harness / model-runtime boundaries intact.
- Constitution V: corpus baselines must not be regenerated by this feature (FR-018).

**Scale/Scope**: stage 1 corpus = 20 documents under `tests/stage1_vendor_identity/`. Single GPU-capable workstation host. Single device per process (feature 014 CF4 / feature 015 FR-006 carry over). One warmup pass per process regardless of corpus size (FR-004).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pass/Fail | Notes |
|---|---|---|
| I. One Repo, Clear Runtime Boundaries | PASS | Pipeline owns the warmup function (`preprocessing/warmup.py`) and the new opt-in CLI surface; harness owns corpus + evaluation, untouched. Model runtime (Ollama) untouched. No cross-boundary collapse. |
| II. Evidence-First, Schema-First | PASS | The four authoritative stage 1 artifacts (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) are unchanged. The `kind: "run_summary"` stdout line is run-level pipeline observability metadata, not a stage 1 output contract — additive `phase_timings.warmup` key with patch `schema_version` bump 0.1.2 → 0.1.3 follows the established additive pattern from feature 014 (0.1.0 → 0.1.1) and feature 015 (0.1.1 → 0.1.2). **Quality Gate #2 inapplicability**: QG#2 ("Changes that affect output contracts must update `docs/stage1-vendor-identity/schemas.md`") does NOT apply because no stage 1 output artifact contract changes; the run_summary additive bump is documented under `pipeline/timing.py` and this feature's `contracts/run-summary-schema.md` rather than `schemas.md`. |
| III. Deterministic Control | PASS | No model-driven decisions added. Opt-in detection (FR-010 / Q1), warmup execution, fail-fast on warmup error, schema-version bump, and CPU/stub warn-and-proceed are all deterministic code. |
| IV. Provenance and Review Safety | PASS | Vendor-identity provenance untouched (this feature only changes preprocessing init/timing surfaces and ships a new docs page). |
| V. Benchmarkable, Reproducible | PASS | Corpus baselines NOT regenerated (FR-018 / SC-008). Single-doc and corpus runs both supported (US1, US2, FR-004). New `phase_timings.warmup` gives reproducible cold-vs-warm cache observability (SC-003). |
| Stage 1 Scope Constraints | PASS | No cross into line items, cloud, or remote escalation. PDF input only. No new latency gate (workstation verification of cold-vs-warm threshold is observability, not a gate per FR-014). |
| Quality Gates 1–7 | PASS | (1) pipeline/harness boundary preserved; (2) `schemas.md` unchanged because no stage 1 output artifact shape changes; (3) `architecture.md` / `ollama-runtime.md` unchanged because runtime topology unchanged — but this feature **adds** `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` (US4 / FR-017 deliverable); (4) verifiable via single-doc + corpus paths (US1 / US2 independent tests); (5) GPU vs CPU lane behavior preserved per WSL/native distinction (FR-013, Constitution V); (6) evaluator inputs unchanged; (7) consistency with target architecture preserved — warmup is a foundational observability primitive for the future trijunction ingestion path. |

**No violations**. The Complexity Tracking table at the bottom is empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-gpu-warmup-miopen-cache/
├── spec.md                         # /speckit.specify (with /speckit.clarify session 2026-05-08, 3 questions resolved)
├── plan.md                         # this file
├── research.md                     # Phase 0 — decisions and rationale (R-016.1 through R-016.10)
├── data-model.md                   # Phase 1 — entities (WarmupPass, phase_timings.warmup, WarmupError, cache state, default env)
├── quickstart.md                   # Phase 1 — cold-cache + warm-cache + CPU-no-op + failure walkthroughs
├── contracts/                      # Phase 1
│   ├── cli-contract.md             # `--gpu-warmup` flag + DARTWING_GPU_WARMUP env var; activation orthogonality with --preprocess-profile
│   ├── module-invariants.md        # warmup-once-per-process, engine-reuse, fail-fast, no-fold-into-per-doc invariants
│   └── run-summary-schema.md       # additive phase_timings.warmup shape; SCHEMA_VERSION 0.1.2 → 0.1.3 codebase-level bump
├── checklists/                     # /speckit.checklist outputs (deferred until /speckit.tasks ↔ /speckit.analyze gates if used)
└── tasks.md                        # /speckit.tasks output (NOT created here)
```

### Source Code (repository root)

```text
src/dartwing_ocr/
├── preprocessing/
│   ├── warmup.py                       # NEW: run_warmup(engine, *, env_overrides=None) -> WarmupResult; deterministic single-pass invocation against the already-adopted engine; raises WarmupError on any MIOpen/COMGR/Paddle exception (FR-007 / SC-011). Owns the canonical warmup-input fixture (R-016.2).
│   ├── errors.py                       # CHANGED: add WarmupError(message: str, cause_class: str, cause_module: str). Mirrors the EngineInitError pattern used by feature 010/014.
│   ├── ocr.py                          # UNCHANGED for warmup mechanics — already exposes _adopt_engine / _ENGINE that warmup.py reuses (no new singleton, no second engine).
│   ├── pipeline.py                     # CHANGED (small): single-doc path optionally calls run_warmup() right after _adopt_engine succeeds and before measure_phase("rasterization") on the first page; passes the captured warmup seconds onto the run_summary record builder when present.
│   └── cli.py                          # CHANGED (small): wires the new `--gpu-warmup` flag; reads `DARTWING_GPU_WARMUP=1` as a fallback; emits the FR-010 stderr warn-and-proceed line on CPU/stub combinations.
├── pipeline/
│   ├── timing.py                       # CHANGED: bump SCHEMA_VERSION 0.1.2 → 0.1.3 (codebase-level per FR-008 / Q2). Extend attach_one_time_gpu_phases() to also emit `warmup` (or add sibling attach_warmup_phase()) when warmup_seconds is provided. _normalize_per_page() and existing flat-key emission unchanged.
│   ├── corpus_run.py                   # CHANGED: between _warm_initialize_live_preprocess succeeding (engine adopted) and the per-document loop, optionally invokes preprocessing.warmup.run_warmup(). On WarmupError, emits the FR-007 stderr line (`warmup failed: <cause>`), exits non-zero, emits no run_summary, processes no documents (SC-011). On success, threads the captured warmup seconds onto the first successful per-document record alongside paddle_import / gpu_bind_probe / engine_init.
│   ├── runner.py                       # CHANGED (small): single-doc path mirrors corpus_run's wiring point — runs warmup once after the engine is adopted, before the first measure_total invocation, and threads the captured seconds into build_per_document_success.
│   └── (profiles.py / stages.py / cli.py unchanged)
└── (everything else unchanged)

tests/
├── preprocessing/
│   ├── test_warmup_unit.py                 # NEW: run_warmup() unit-tests with stubbed engine — exactly one predict() call; deterministic input shape; WarmupError wraps any underlying exception with cause_class/cause_module preserved. CPU-safe (no GPU required).
│   └── test_warmup_cpu_no_op.py            # NEW: --gpu-warmup + ppstructurev3@cpu (and stub adapter) emits stderr warn-and-proceed line, no warmup pass, no env var mutation, no cache access; identical exit to non-opt-in run (FR-010 / SC-007).
├── pipeline/
│   ├── test_run_summary_schema_0_1_3.py    # NEW: schema_version is exactly "0.1.3" on every run of the new binary regardless of warmup state; phase_timings.warmup absent without warmup; phase_timings.warmup = {seconds: <float>} present and on first successful doc only when warmup ran (FR-008 / SC-005). CPU-safe via stub adapter.
│   ├── test_warmup_engine_reuse.py @gpu    # NEW: warmup-enabled GPU run on inv_001_easy/source.pdf — PPStructureV3 constructed exactly once (preserves feature 015 SC-001); warmup pass runs strictly after engine adoption and strictly before first measure_phase("rasterization"); resulting preprocess_output.json sha256 equals non-warmup run (FR-018 / SC-008).
│   ├── test_warmup_first_doc_exclusion.py @gpu  # NEW: first-doc phase_timings.total / rasterization / per_page_inference[*].seconds / artifact_write all exclude warmup duration (SC-004).
│   ├── test_warmup_corpus_once.py @gpu     # NEW: ≥ 2-document warm corpus run with --gpu-warmup — phase_timings.warmup appears on exactly the first successful per-document entry, on no other entry (FR-004 / SC-005).
│   ├── test_warmup_cold_vs_warm.py @gpu    # NEW: two consecutive warmup-enabled processes on the same fixture, first preceded by clearing ~/.cache/miopen + ~/.cache/comgr; cold seconds ≥ 2× warm seconds (SC-003 placeholder; threshold pinned by R-016.3 measurements).
│   └── test_warmup_failure_path.py @gpu    # NEW: warmup-pass failure injection — exits non-zero with stderr `warmup failed: <cause>`; no run_summary emitted; no phase_timings.warmup; no preprocess_output.json written; no silent downgrade (SC-011).
└── contract_tests/                          # existing v1.2.0 contract tests — must continue to pass unchanged (FR-018).

docs/
└── stage1-vendor-identity/
    └── gpu-warmup-and-cache.md             # NEW (US4 / FR-017 / SC-009): cache locations (~/.cache/miopen, ~/.cache/comgr); how to clear them; how to read phase_timings.warmup as cold-vs-warm signal; MIOPEN_FIND_MODE default rationale; per FR-016 hybrid policy — list "addressed by default config" (env vars/settings shipped) vs "residual / known diagnostic" (meaning + operator guidance).
```

**Structure Decision**: single Python package, **one new module** (`preprocessing/warmup.py`), **one new error type** (`WarmupError` in `preprocessing/errors.py`), **four touched modules** (`preprocessing/pipeline.py`, `preprocessing/cli.py`, `pipeline/timing.py`, `pipeline/corpus_run.py`, `pipeline/runner.py` — five if you count `runner.py`'s small wiring change). **No new top-level subpackage.** The warmup phase contract lives entirely under `pipeline/timing.py` (the `RunSummary` codebase-level `SCHEMA_VERSION = "0.1.3"` plus the extended `attach_one_time_gpu_phases`), keeping the run_summary schema as the single source of truth for run-level observability. The `--gpu-warmup` opt-in lives in the existing preprocess CLI rather than a new entry point, mirroring how feature 014 added `--preprocess-profile` rather than spinning up a separate preflight CLI.

## Complexity Tracking

> No Constitution violations. Table left intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
