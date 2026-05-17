# Phase 0 Research: GPU Engine Reuse And Phase Timing

This document resolves every NEEDS CLARIFICATION implied by the spec and Technical Context. The clarification session of 2026-05-07 already pinned five user-facing decisions (Q1–Q5); the items below are the engineering-side decisions needed before Phase 1 design.

## R-015.1 — Engine reuse strategy: persist preflight-constructed engine into runtime singleton

**Decision**: When `classify(attempt_ppstructurev3_init=True)` succeeds, persist the constructed `PPStructureV3` instance into `dartwing_ocr.preprocessing.ocr._ENGINE` (and set `_ENGINE_DEVICE` to `"gpu:0"`) instead of `del`-ing it. The runtime helper `ocr._get_engine(device="gpu:0")` returns the persisted instance on its first call rather than constructing a fresh one. The single-device-per-process guard (CF4 from feature 014) remains enforced via the same `_ENGINE_DEVICE` check.

**Rationale**:
- FR-002 explicitly allows the option "preflight and runtime share one process-scoped engine." Persisting the preflight engine collapses the duplicate ~50 s init that today fires twice per process.
- Runtime ergonomics stay identical: callers still go through `ocr.run_page → _get_engine(device=…)`. They don't need to know whether the engine came from preflight or from lazy runtime construction.
- The standalone preflight CLI's `--no-init` knob is preserved verbatim — when the operator opts out of step 6, no engine is persisted and the runtime path constructs lazily on first `run_page` (this is the `PPSTRUCTUREV3_INIT_SUCCEEDED` + `ppstructurev3_init_skipped_reason="caller_disabled_init_attempt"` branch in classify()).
- Honors the FR-001 invariant ("one process MUST construct PPStructureV3 no more than once") even in the worst case (single-doc cold run: classify constructs, runtime reuses; no second construction).

**Alternatives considered**:
- *Skip step 6 in the runtime gate, rely on lazy runtime construction*: would lose the fail-fast `PPSTRUCTUREV3_INIT_FAILED` state for hosts with broken PaddleOCR builds. SC-007's 10 s budget would still be met, but the failure would surface mid-document instead of pre-document, which is harder to diagnose. Rejected.
- *Have classify() return the engine to the caller and stash it in `corpus_run._WARM_ENGINE`*: works for the warm-corpus path but the single-doc CLI (`preprocessing/cli.py`) does not go through the warm registry. Two stash locations means two reuse paths means two ways to leak. Rejected — `ocr._ENGINE` is the existing single canonical home.

**Implementation notes**:
- `classify()` step 6 changes: instead of `_engine = PPStructureV3(...); del _engine`, do `engine = PPStructureV3(...); ocr._ENGINE = engine; ocr._ENGINE_DEVICE = "gpu:0"`. Wrap the cross-module assignment in a tiny helper (`ocr._adopt_engine(engine, device)`) so the import is one-way (preflight depends on ocr; ocr does not depend on preflight) and easier to mock in tests.
- The `_PADDLE_SEEDED` flag in `ocr.py` should be set to True after preflight persists, so a later `_get_engine()` call doesn't re-seed Paddle (idempotent, but cleaner).

## R-015.2 — Per-step timing inside classify()

**Decision**: `classify()` measures three new phases via `time.perf_counter_ns()` deltas around steps 2 (paddle import), 5 (bind probe), and 6 (PPStructureV3 init). Results are surfaced via three new fields on `PreflightEvidence`: `paddle_import_seconds: Optional[float]`, `gpu_bind_probe_seconds: Optional[float]`, plus the existing `ppstructurev3_init_seconds`. Each is `None` when the corresponding step did not execute (early-exit on a fail state).

**Rationale**:
- FR-013 requires distinct timings for paddle import, GPU bind probe, and engine init. The existing code already times step 6 only (`ppstructurev3_init_seconds`); adding two more fields is cheap and keeps all GPU-readiness timings on the same evidence record.
- `Optional[float]` matches the existing pattern for `ppstructurev3_init_seconds` and serializes naturally to `null` in JSON, satisfying FR-016 (omit / null when not performed).
- `time.perf_counter_ns()` is monotonic per Clarification Q3.

**Alternatives considered**:
- *Time the steps inside corpus_run.py around `ensure_gpu_ready()`*: doesn't decompose paddle_import vs bind_probe vs engine_init since classify is one call. Rejected.

**Schema**: PreflightEvidence is internal to the pipeline and is not part of the stage 1 contract set; adding optional fields requires no contract amendment.

## R-015.3 — Per-page inference timing shape

**Decision**: Replace the global `(_GPU_INFERENCE_NS_TOTAL, _GPU_INFERENCE_PAGES)` accumulator in `preprocessing/ocr.py` with a list `_GPU_INFERENCE_NS_BY_PAGE: list[tuple[int, int]]` of `(page_number, elapsed_ns)` records appended on each `engine.predict` call. Add a new drain helper `take_gpu_inference_per_page() -> list[tuple[int, float]] | None` that returns `[(page_1based, seconds_rounded_6dp), …]` and resets the list. The legacy `take_gpu_inference_seconds()` helper stays in place for one schema version (back-compat for any external caller) and is implemented as `sum(seconds for _, seconds in (take_gpu_inference_per_page() or []))`.

**Rationale**:
- FR-013 requires per-page entries (one per page). Q3 pinned the shape: `per_page_inference: [{page: 1, seconds: 0.31}, …]`.
- Page numbers must be 1-based to match `preprocess_output.json`'s page numbering (Q3 explicit + existing convention in `pipeline.py`'s `pr.page_number` which is 1-based per `rasterize.rasterize_pdf`).
- Keeping the legacy summing helper avoids breaking anything in feature 014's `gpu_inference_seconds` flat-key emission until a future feature retires it.

**Alternatives considered**:
- *Threading a per-document timing object directly into `run_page`*: cleaner functionally but enlarges the function signature. The existing module-level accumulator pattern is already in place; extending it from "scalar" to "list" is the smaller diff. Rejected larger refactor.

## R-015.4 — Run summary schema bump 0.1.1 → 0.1.2

> **Single source of truth**: the canonical FR-013 phase vocabulary is defined in `spec.md §FR-013`. Phase keys enumerated below are derived from that list. If they ever drift, `spec.md §FR-013` wins.

**Decision**: Bump `pipeline.timing.SCHEMA_VERSION` from `"0.1.1"` to `"0.1.2"`. Per-document records gain two additive fields:

- `phase_timings: {<name>: {seconds: <float>}}` — keyed phase name, scalar phases. Names: `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup` (optional, omitted when not performed per Q2/FR-016), `rasterization`, `artifact_write`, `total`. One-time phases (`paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`) appear only on the **first successful** per-document entry per process. Per-document phases (`rasterization`, `artifact_write`, `total`) appear on every per-document entry.
- `per_page_inference: [{page: <int>, seconds: <float>}, …]` — 1-based `page`, `time.perf_counter()`-derived seconds. Present on every per-document entry that ran any per-page inference; absent (key omitted) on entries that aborted before any page ran.

The existing flat keys (`stages.preprocess.total_seconds`, `gpu_init_seconds`, `gpu_inference_seconds`) **stay** in the per-document record for one schema version. Consumers built against 0.1.1 continue to read flat keys; consumers built against 0.1.2 may use the structured `phase_timings` / `per_page_inference` blocks instead. The eventual flat-key removal is **not** part of this feature.

**Rationale**:
- FR-014 requires "additive way only" — keep both shapes for one version.
- Patch-version bump matches the pattern from feature 014 (`0.1.0 → 0.1.1` for `preprocess_lane` / `gpu_init_seconds` / `gpu_inference_seconds` / `gpu_lane_forced_abort`).
- The new shape exactly mirrors Clarification Q3's pin: structured records with `seconds: float` keys, 1-based per-page array.

**Alternatives considered**:
- *Major bump 0.1.1 → 0.2.0 with simultaneous flat-key removal*: violates FR-014 ("additive only"). Rejected.
- *Minor bump 0.1.1 → 0.2.0*: minor bumps in this codebase have signaled material consumer-visible reshaping; the change here is purely additive, so patch is more honest. Rejected minor.

## R-015.5 — Phase emission on failed documents (Clarification Q5)

**Decision**: `build_per_document_failure(...)` accepts an additional optional `phase_timings: dict | None` and `per_page_inference: list | None` keyword. When non-None, those keys appear on the failure record. A per-document failure mid-inference therefore emits whatever phases completed (e.g. `rasterization` set; `per_page_inference` arrayed up to and including the failed page) plus the existing `status: "failure"` + `failed_stage` + `exit_code` + `message` triple. Phases that did not run are **omitted** from the dict (not set to zero, not set to null), matching FR-016.

**Rationale**:
- Q5 answer: "carrying whatever `phase_timings` completed before the failure plus an explicit failure status field."
- `status: "failure"` is the existing explicit failure signal — no new field needed.
- The omission convention (key absent ⇒ phase not performed) is already established as R-009 in feature 011 / 014.

**Alternatives considered**:
- *Always include all phase keys with `null` seconds when a phase didn't run*: contradicts FR-016 ("absent phases MUST be omitted rather than reported as zero"). Rejected.

## R-015.6 — Single-document CLI surface for phase timings

**Decision**: The single-document path (`preprocessing/cli.py`) emits a one-shot `kind: "run_summary"` line with `documents_total: 1`, `documents_succeeded: 1` (or 0), and a single `per_document` entry containing the same `phase_timings` + `per_page_inference` shape used in corpus mode. This unifies the observability surface across single-doc and corpus modes; SC-005 ("identify the slowest phase from output alone") works the same way regardless of how the run was launched.

**Rationale**:
- FR-014 specifies the run_summary stdout line as the carrier. The single-doc CLI today does not emit a run_summary; it would be confusing to surface phase_timings only in corpus mode.
- A trivial RunSummary with one entry is the cheapest unification — no new code path.

**Alternatives considered**:
- *Single-doc CLI emits a different `kind: "single_doc_summary"` line*: contradicts the Q1 clarification ("do not introduce a new stdout `kind`"). Rejected.
- *Single-doc CLI emits no run_summary; phase timings only available via corpus mode*: violates FR-014 ("each preprocessing run") and SC-004 ("every successful preprocessing run output"). Rejected.

## R-015.7 — Fail-fast budget verification (SC-007 ≤ 10 s)

**Decision**: No code change required for the budget itself; verify with a regression test on the `PADDLE_NOT_INSTALLED` and `GPU_NOT_EXPOSED` paths using the existing `gpu` pytest marker. The test asserts `time.perf_counter() - t0 <= 10.0` from CLI entrypoint to non-zero exit. On hosts without GPU, both states are exercisable.

**Rationale**:
- The existing `classify()` early-exit ladder hits a fail state in steps 1–5, all of which are sub-second probes (Paddle import being the heaviest at ~1–3 s). 10 s is comfortable.
- The PPStructureV3 init (step 6) is the only multi-second step, and it is *only* reached on the success path — fail states never spend time there.
- The cached `_LAST_READOUT` short-circuits any subsequent calls, so a multi-document run on a broken host hits ≤ 10 s on doc 1 and ~0 ms thereafter.

## R-015.8 — CPU and stub isolation (FR-017–FR-019, SC-006, SC-008)

**Decision**: No change to today's CPU and stub paths beyond purely additive per-document `phase_timings` carrying CPU-only phase names (`rasterization`, `artifact_write`, `total`). CPU runs **must not** emit `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, or `per_page_inference` entries, since those probes do not run. The omission rule (FR-016) handles this naturally: `corpus_run.py` only sets the GPU one-time keys when `_resolved_preprocess_lane.startswith("gpu")` and `_PREFLIGHT_READOUT is not None`.

**Rationale**:
- The existing feature-014 logic already conditions `gpu_init_seconds` and `gpu_inference_seconds` on the GPU lane; the new structured form follows the same gate.
- Stub adapter paths short-circuit before live preprocessing runs — they do not enter `_warm_initialize_live_preprocess`, do not call `ensure_gpu_ready()`, do not invoke `ocr.run_page`. Phase-timing emission therefore never references GPU phases on a stub run.

## Open questions resolved

All NEEDS CLARIFICATION flags are resolved by R-015.1 through R-015.8 plus the spec's Clarifications session:

| Source | Question | Resolution |
|---|---|---|
| Spec Q1 | Where do phase timings surface? | run_summary stdout, per-document, no new `kind`, no preprocess_output.json change. (R-015.4) |
| Spec Q2 | Is MIOpen/COMGR warmup implemented? | No — reserved phase only. (R-015.4 keys list, FR-012/FR-013) |
| Spec Q3 | What shape do entries take? | Structured `{seconds: float}` records; per_page_inference array; 1-based pages; `time.perf_counter()` monotonic. (R-015.3, R-015.4) |
| Spec Q4 | What is the fail-fast budget? | ≤ 10 s wall-clock from process start. (R-015.7) |
| Spec Q5 | Failed-document emission? | Failure entry includes partial `phase_timings` + `per_page_inference`, omits unperformed phases. (R-015.5) |
| Engineering | How to dedupe init? | Persist preflight engine into `ocr._ENGINE`. (R-015.1) |
| Engineering | How to time paddle_import / bind_probe? | New optional fields on PreflightEvidence. (R-015.2) |
| Engineering | Schema bump strategy? | 0.1.1 → 0.1.2 patch, additive only. (R-015.4) |
| Engineering | Single-doc emission path? | Same RunSummary shape with documents_total=1. (R-015.6) |
| Engineering | CPU/stub isolation? | Existing GPU-lane conditional gates carry over. (R-015.8) |
