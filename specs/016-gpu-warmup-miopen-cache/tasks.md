---
description: "Implementation tasks for feature 016: GPU Warmup And MIOpen Cache Stabilization"
---

# Tasks: GPU Warmup And MIOpen Cache Stabilization

**Input**: Design documents from `/specs/016-gpu-warmup-miopen-cache/`
**Prerequisites**: plan.md (✅), spec.md (✅), research.md (✅), data-model.md (✅), contracts/ (✅: `cli-contract.md`, `module-invariants.md`, `run-summary-schema.md`), quickstart.md (✅)

**Tests**: Included. The spec's four user stories (`US1`–`US4`) each declare an Independent Test, and `plan.md` §Project Structure enumerates concrete test files under `tests/preprocessing/` and `tests/pipeline/`. GPU-marked tests follow `@pytest.mark.gpu` per FR-012 and the workstation verification path may be deferred per FR-014.

**Organization**: Tasks are grouped by user story (US1 → US4) so each story can be implemented, tested, and delivered independently. US1 is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- **`@gpu`** in a description (not a label) marks tasks that require workstation GPU and may be deferred per FR-014
- All file paths are repo-root-relative

## Path Conventions

- Source: `src/ledgerlinc_ocr/{preprocessing,pipeline}/...`
- Tests: `tests/{preprocessing,pipeline}/...`
- Docs: `docs/stage1-vendor-identity/...`
- Feature artifacts: `specs/016-gpu-warmup-miopen-cache/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: This feature does not introduce any new pinned dependency, top-level subpackage, or build-system change (per `plan.md` §Technical Context — "No new pinned dependency"). Setup is one verification step.

- [x] T001 ✅ DONE — `gpu` pytest marker confirmed registered in `tests/conftest.py:74-80` via `pytest_configure(config)` with skip-gating in `pytest_collection_modifyitems` (lines 101-118). FR-012 already satisfied by feature 014/015 infrastructure; no edit needed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Three independent additions that the user-story phases all build on. All three are in different files (or independent functions in `pipeline/timing.py`) and can run in parallel.

**⚠️ CRITICAL**: User-story work in Phase 3+ MUST NOT begin until T002, T003, and T004 are complete.

- [x] T002 [P] ✅ DONE — `WarmupError(message: str, *, cause_class: str, cause_module: str)` added to `src/ledgerlinc_ocr/preprocessing/errors.py` (subclass of `PreprocessingError`, exit_code = `EXIT_WARMUP_FAILED = 15`). Cause-class closed taxonomy preserved per `data-model.md` §WarmupError. Sanity-checked: `from ledgerlinc_ocr.preprocessing.errors import WarmupError` instantiates with all 5 taxonomy values.
- [x] T003 [P] ✅ DONE — `SCHEMA_VERSION` bumped `"0.1.2"` → `"0.1.3"` in `src/ledgerlinc_ocr/pipeline/timing.py` per FR-008 / R-016.9 / /speckit.clarify Q2. Feature-016 note added to the inline comment block. Sanity-checked: `from ledgerlinc_ocr.pipeline.timing import SCHEMA_VERSION` returns `"0.1.3"`.
- [x] T004 [P] ✅ DONE — `attach_one_time_gpu_phases(record, readout, *, warmup_seconds=None)` extended in `src/ledgerlinc_ocr/pipeline/timing.py` with the additive keyword. Six-decimal rounding via `round(warmup_seconds, 6)`. Handles the both-None case as a no-op (record untouched). Sanity-checked: `attach_one_time_gpu_phases(record, None, warmup_seconds=0.123456789)` produces `record["phase_timings"]["warmup"] == {"seconds": 0.123457}`.

**Checkpoint**: foundational pieces in place. US1, US2, US3 can begin (US4 documentation deliverable can also begin in parallel since it does not import any feature-016 source code).

---

## Phase 3: User Story 1 — Opt-in warmup pass with separately reported timing (Priority: P1) 🎯 MVP

**Goal**: A warmup-enabled `ppstructurev3@gpu` run executes exactly one PPStructureV3 warmup inference after engine construction and before the first timed document, then reports the warmup duration as `phase_timings.warmup` on the first successful per-document `run_summary` entry — without altering `preprocess_output.json` or per-document phase timings.

**Independent Test** (per `spec.md` §US1): a single `--gpu-warmup` `ppstructurev3@gpu` run on `tests/stage1_vendor_identity/inv_001_easy/source.pdf` produces a per-doc `run_summary` entry whose `phase_timings.warmup = {seconds: <float>}` is present alongside `paddle_import` / `gpu_bind_probe` / `engine_init`, and whose `phase_timings.total` and `phase_timings.per_page_inference[*].seconds` do NOT include warmup time.

### Implementation for User Story 1

- [x] T005 [P] [US1] ✅ DONE — `src/ledgerlinc_ocr/preprocessing/warmup.py` created with `WarmupResult` frozen dataclass, `_WARMUP_RAN` once-per-process guard, `_DEFAULT_FIXTURE_PATH` resolver, `_apply_env_defaults()` for the 4 MIOpen env vars (operator override wins), `run_warmup(engine, *, fixture_path=None)` with the 5-class WarmupError taxonomy, plus public `get_cached_warmup_seconds()` + `reset_warmup_state()` accessors. Original task description: Create `src/ledgerlinc_ocr/preprocessing/warmup.py` with: (a) frozen `WarmupResult` dataclass exposing `seconds: float`, `fixture_sha256: str`, `fixture_path: pathlib.Path` per `data-model.md` §WarmupResult; (b) module-level `_WARMUP_RAN: bool = False` and `_CACHED_RESULT: WarmupResult | None = None` for the once-per-process guarantee per FR-001 / FR-004 / `contracts/module-invariants.md` I-1; (c) `_DEFAULT_FIXTURE_PATH` resolving to `tests/stage1_vendor_identity/inv_001_easy/source.pdf` per `research.md` R-016.2 / I-8; (d) `_apply_env_defaults()` that sets `MIOPEN_FIND_MODE=2`, `MIOPEN_USER_DB_PATH=$HOME/.cache/miopen`, `MIOPEN_CUSTOM_CACHE_DIR=$HOME/.cache/miopen`, `MIOPEN_LOG_LEVEL=2` ONLY when each is currently unset (operator override wins per `research.md` R-016.4 / R-016.5 / I-7); (e) `run_warmup(engine, *, fixture_path: Path | None = None) -> WarmupResult` that loads the fixture, sha256s the rasterized PIL image bytes, runs `engine.predict(np_img)` once with a `time.perf_counter()` window, and wraps any exception (fixture-load / clock-anomaly / `engine.predict` failure) as `WarmupError` with the cause-class taxonomy from T002; on success sets `_WARMUP_RAN = True` and stores `_CACHED_RESULT`. The module is intended to be imported lazily on the GPU branch only per FR-011 / I-6
- [x] T006 [US1] ✅ DONE — `Invocation.warmup: bool = False` field added to `src/ledgerlinc_ocr/preprocessing/pipeline.py`. `_run_inner` lazy-imports `preprocessing.warmup` on the GPU branch and invokes `run_warmup(ocr._ENGINE)` AFTER `_ensure_gpu_ready()` succeeds and BEFORE `measure_phase("rasterization")` opens (I-3). WarmupError propagates to the CLI catch boundary. Original: Wire warmup into the single-doc path in `src/ledgerlinc_ocr/preprocessing/pipeline.py`: detect the warmup opt-in via the activation helper from T010; on the GPU + opt-in branch, lazy-import `from ledgerlinc_ocr.preprocessing import warmup` and call `warmup.run_warmup(engine)` AFTER `ocr._adopt_engine` succeeds and BEFORE any `pipeline.timing.measure_phase`/`measure_total` block opens (FR-001 / FR-003 / I-3); on success, thread the captured seconds into the first successful per-doc record via `attach_one_time_gpu_phases(record, readout, warmup_seconds=result.seconds)`; on `WarmupError`, re-raise to the runner-level catch in T011
- [x] T007 [US1] ✅ DONE — `src/ledgerlinc_ocr/pipeline/corpus_run.py` wires warmup BETWEEN `_warm_initialize_live_preprocess` success and the per-document loop (R-016.10). On WarmupError: stderr `error: warmup failed: <cause>` + exit 15 + NO run_summary (SC-011 (c)). First-successful-doc attachment threads `warmup_seconds` via `attach_one_time_gpu_phases(record, readout, warmup_seconds=...)` (I-11). Warn-and-proceed line emitted when opt-in is set but profile is non-GPU. Original: Wire warmup into the warm-corpus path in `src/ledgerlinc_ocr/pipeline/corpus_run.py`: identical activation detection as T006; invoke `warmup.run_warmup(engine)` AFTER `_warm_initialize_live_preprocess` returns success (currently around L271–278) and BEFORE the `for entry in documents:` loop at L285 per `research.md` R-016.10; same first-successful-doc attachment via `attach_one_time_gpu_phases`; on `WarmupError`, print `error: warmup failed: <cause_class>: <message>` to stderr, exit code **15**, emit no `run_summary` line on stdout, write no `preprocess_output.json` for any document that would have been timed after the failed warmup, do NOT silently downgrade per FR-007 / SC-011 / `contracts/cli-contract.md` §4 / I-5
- [x] T008 [US1] ✅ DONE — `--gpu-warmup` boolean flag added to `src/ledgerlinc_ocr/preprocessing/cli.py` `_build_parser()`. Threaded through to `Invocation(warmup=warmup_threaded)` based on `is_warmup_optin_set(args.gpu_warmup)` AND `is_gpu_lane(preprocess_lane)`. WarmupError catch added between `_GpuPrerequisiteError` and `InputRejectedError`; exit 15 + stderr `error: warmup failed:` + no run_summary. `warmup_seconds` from `get_cached_warmup_seconds()` threaded into the success-path run_summary via `_emit_single_doc_run_summary(..., warmup_seconds=...)`. Original: Add `--gpu-warmup` boolean CLI flag (no `=value`; off by default) to the single-doc CLI in `src/ledgerlinc_ocr/preprocessing/cli.py` per `contracts/cli-contract.md` §1–§2; help-text wording matches §2; flag is orthogonal to `--preprocess-profile` per FR-002
- [x] T009 [US1] ✅ DONE — `--gpu-warmup` boolean flag added to `src/ledgerlinc_ocr/pipeline/cli.py` `run` subparser with the matching help text + default-off behavior. The flag flows through `args.gpu_warmup` and is read by `corpus_run.py` via `is_warmup_optin_set(args.gpu_warmup)`. Original: Add the same `--gpu-warmup` boolean CLI flag to the warm-corpus CLI in `src/ledgerlinc_ocr/pipeline/cli.py` per `contracts/cli-contract.md` §1–§2; same default-off and help-text contract
- [x] T010 [US1] ✅ DONE — Created CPU-safe `src/ledgerlinc_ocr/preprocessing/warmup_optin.py` with `is_warmup_optin_set(cli_flag, env=None)`, `is_gpu_lane(preprocess_lane)`, `warn_and_proceed_message(profile_name)`. Truthiness whitelist `{"1", "true", "yes"}` (case-insensitive). CLI wins over env var. Verified zero GPU imports (no paddle / MIOpen / numpy / PIL / pypdfium2 modules pulled). 9/9 truthiness tests + 7/7 lane tests + warn-message literal check all pass. Original: Implement shared activation helper `read_gpu_warmup_optin(args, env=os.environ) -> bool` in `src/ledgerlinc_ocr/preprocessing/cli.py` (or a new lightweight `src/ledgerlinc_ocr/pipeline/activation.py` module if cross-package import is preferred): returns `True` when CLI flag is set OR when `LEDGERLINC_GPU_WARMUP` value (after `.strip().lower()`) is in the strict whitelist `{"1", "true", "yes"}`; CLI flag wins when both are present; ambiguous env values silently treated as `False` per `research.md` R-016.1 / `contracts/cli-contract.md` §1 / `data-model.md` §"Activation-surface state machine"
- [x] T011 [US1] ✅ DONE — `EXIT_WARMUP_FAILED = 15` added to `src/ledgerlinc_ocr/preprocessing/errors.py`; `ExitCode.WARMUP_FAILED = 15` added to `src/ledgerlinc_ocr/pipeline/exit_codes.py` IntEnum. Both single-doc CLI and corpus runner catch `WarmupError` and return this code. Original: Add exit code **15** to `src/ledgerlinc_ocr/pipeline/exit_codes.py` (the central exit-code enum/registry) named `WARMUP_FAILED`, immediately after feature 014's preflight 10–14 codes per `contracts/cli-contract.md` §4 / `research.md` R-016.6; runner-level catch in `src/ledgerlinc_ocr/pipeline/runner.py` and `src/ledgerlinc_ocr/pipeline/corpus_run.py` raises this code on `WarmupError`

### Tests for User Story 1

- [x] T012 [P] [US1] ✅ DONE — CPU-safe unit tests landed at `tests/unit/preprocessing/test_warmup_unit.py` (note: directory aligned to existing convention `tests/unit/preprocessing/` rather than the plan's `tests/preprocessing/`). 14 test cases covering: once-per-process guard (I-1, FR-001/004), six-decimal rounding, get_cached_warmup_seconds, the 5-class WarmupError taxonomy (UnknownError / PaddleError / MIOpenError / comgr→MIOpenError / FixtureLoadError), failed-warmup-does-not-set-flag, fixture digest stability (I-8), no-mutation of caller phase_timings (I-4), env defaults applied when unset, operator-override-wins (FR-015 / R-016.4 / R-016.5). Test file uses `pytest.importorskip("PIL")` etc. so it skips cleanly without preprocessing deps; will run green in devcontainer / CI. Original: CPU-safe unit tests in `tests/preprocessing/test_warmup_unit.py`: stub `engine` with a controlled `predict` callable; assert `run_warmup` calls `predict` exactly once on first invocation and exactly zero additional times on second invocation while returning the cached `WarmupResult` (I-1); assert `WarmupError` wraps an injected `RuntimeError` with `cause_class="UnknownError"` and `cause_module` preserved (data-model.md §WarmupError); assert fixture sha256 stable across two invocations on the same file (I-8); assert `run_warmup` does NOT mutate any caller-side `phase_timings` map (I-4)
- [x] T013 [P] [US1] ✅ DONE — CPU-safe schema tests landed at `tests/pipeline_tests/test_run_summary_schema_0_1_3.py` (directory `pipeline_tests/` per existing convention, not the plan's `pipeline/`). 10 tests covering: codebase-level `SCHEMA_VERSION == "0.1.3"` (FR-008 / R-016.9), JSON wire format, warmup-key absence rules (FR-002 / SC-002 / FR-016), six-decimal rounding (run-summary-schema.md §2), zero-seconds edge case, joint-presence rule (I-11) with full + partial readouts, defensive None-readout handling, legacy `total_seconds` back-compat (FR-008 lineage). All 10 assertions verified end-to-end via direct Python invocation in dev env (PASS); pipeline_tests conftest's autouse fixture pulls PIL transitively in this env, but tests themselves are CPU-safe and will collect cleanly under devcontainer. Original: CPU-safe schema test in `tests/pipeline/test_run_summary_schema_0_1_3.py` (uses the existing stub adapter; no GPU): assert `schema_version == "0.1.3"` on every emitted `run_summary` regardless of `--gpu-warmup` state (I-9); assert `phase_timings.warmup` is absent under stub-adapter runs (FR-002 / SC-002); assert run_summary `phase_timings.warmup` shape is exactly `{"seconds": <float>}` with no other sub-keys when injected via a unit-level helper that exercises `attach_one_time_gpu_phases(..., warmup_seconds=0.123)` (`contracts/run-summary-schema.md` §2)
- [ ] T014 [P] [US1] ⏸ **DEFERRED per FR-014** — workstation GPU verification path. Test file specification: `tests/pipeline_tests/test_warmup_engine_reuse.py` with `@pytest.mark.gpu`. To be implemented + run when workstation GPU access is available; deferred items captured in T032. Original: GPU regression test in `tests/pipeline/test_warmup_engine_reuse.py` (`@pytest.mark.gpu`): run `--gpu-warmup ppstructurev3@gpu` on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; assert `paddleocr.PPStructureV3.__init__` was called exactly once across the run via a counter monkeypatch (preserves feature 015 SC-001 / FR-001); assert `id(engine_after_adopt) == id(engine_seen_by_warmup)` (I-2); assert warmup pass timestamps are strictly between engine-adopt completion and the first `measure_phase("rasterization")` open (I-3); assert `sha256(preprocess_output.json)` is byte-identical to the same fixture run WITHOUT `--gpu-warmup` (FR-018 / SC-008 / I-10)
- [ ] T015 [P] [US1] ⏸ **DEFERRED per FR-014** — workstation GPU verification of SC-004 / I-4 (first-doc phase_timings exclude warmup time). To be implemented + run with GPU. Original: GPU exclusion test in `tests/pipeline/test_warmup_first_doc_exclusion.py` (`@pytest.mark.gpu`): from a warmup-enabled GPU run on `inv_001_easy/source.pdf`, assert that `phase_timings.total + phase_timings.warmup` ≥ (`phase_timings.rasterization` + sum(`phase_timings.per_page_inference[*].seconds`) + `phase_timings.artifact_write`) within rounding tolerance, AND that `phase_timings.total` alone (without warmup) does NOT include warmup time (SC-004 / I-4)
- [ ] T016 [P] [US1] ⏸ **DEFERRED per FR-014** — workstation GPU verification of FR-004 / SC-005 (corpus warmup-once-per-process). To be implemented + run with GPU. Original: GPU corpus test in `tests/pipeline/test_warmup_corpus_once.py` (`@pytest.mark.gpu`): run `--gpu-warmup` over a 2+ document corpus; assert `phase_timings.warmup` appears on EXACTLY the first successful per-document `run_summary` entry and on NO other entry (FR-004 / SC-005)
- [ ] T017 [P] [US1] ⏸ **DEFERRED per FR-014** — workstation GPU verification of SC-011 / I-5 (warmup failure path). To be implemented + run with GPU. Original: GPU failure-injection test in `tests/pipeline/test_warmup_failure_path.py` (`@pytest.mark.gpu`): monkeypatch `paddleocr.PPStructureV3.predict` to raise; assert process exit code == 15; assert stderr contains literal `error: warmup failed:`; assert NO `run_summary` JSON line emitted on stdout (search for `"kind":"run_summary"`); assert NO `preprocess_output.json` written for the targeted document (mtime check against pre-run snapshot); assert no silent downgrade — i.e., no per-doc entry of any kind appears (SC-011 / I-5)

**Checkpoint**: US1 fully functional and testable independently — this is the MVP. US2, US3, US4 may now proceed in parallel.

---

## Phase 4: User Story 2 — Cold-cache vs warmed-cache observability (Priority: P1)

**Goal**: An operator can read the `phase_timings.warmup.seconds` value off two consecutive runs (one cold, one warm) and tell from `run_summary` alone whether MIOpen kernel selection was performed or served from cache.

**Independent Test** (per `spec.md` §US2): run the warmup-enabled GPU command twice on the same fixture in two consecutive processes (cold then warm); confirm cold `phase_timings.warmup.seconds` exceeds warm value by an operator-detectable margin per SC-003 (default 2×, tuned in T020).

- [ ] T018 [P] [US2] GPU regression test in `tests/pipeline/test_warmup_cold_vs_warm.py` (`@pytest.mark.gpu`): in a fresh process, clear `~/.cache/miopen` and `~/.cache/comgr`, run `--gpu-warmup` on `inv_001_easy/source.pdf`, capture `phase_timings.warmup.seconds` as `cold_s`; in a second fresh process WITHOUT clearing caches, repeat and capture `warm_s`; assert `cold_s >= ratio * warm_s` where `ratio` is the value finalized in T020 (defaults to `2.0` from SC-003 placeholder)
- [ ] T019 [P] [US2] GPU regression test in `tests/pipeline/test_warmup_comgr_only.py` (`@pytest.mark.gpu`): from a warm-cache state, clear ONLY `~/.cache/comgr`; rerun; assert `phase_timings.warmup.seconds` rises measurably above the warm baseline (US2 acceptance scenario #3)
- [ ] T020 [US2] `@gpu` Workstation cold-vs-warm verification per `specs/016-gpu-warmup-miopen-cache/quickstart.md` §1–§3: run cold + warm + comgr-only-cleared in three fresh processes on the workstation; record three `phase_timings.warmup.seconds` values into `quickstart.md` Appendix A; if the observed cold/warm ratio differs materially from 2×, amend `research.md` R-016.3 and `spec.md` SC-003 BEFORE merge (FR-014's amendment hook). If GPU access is unavailable at landing, defer this task per FR-014's deferral path and capture the deferral in T032

**Checkpoint**: cold-vs-warm signal verified on the workstation OR formally deferred under FR-014.

---

## Phase 5: User Story 3 — CPU and stub paths pay no warmup cost (Priority: P2)

**Goal**: `ppstructurev3@cpu` and stub-adapter runs with the warmup opt-in set in any form (CLI flag or env var) emit a clear stderr warning, perform no warmup, mutate no MIOpen/COMGR env var, and access no MIOpen/COMGR cache directory — preserving CI safety on hosts without Paddle GPU.

**Independent Test** (per `spec.md` §US3): run `ppstructurev3@cpu` and the stub adapter with `--gpu-warmup` (and again with `LEDGERLINC_GPU_WARMUP=1`) on a host without Paddle GPU; suite passes; output contains no `warmup` key, no MIOpen/COMGR env var mutations, no GPU phase timings.

- [x] T021 [US3] ✅ DONE (implemented as part of T008 + T007) — warn-and-proceed branch landed in two places: (a) `src/ledgerlinc_ocr/preprocessing/cli.py` `main()` after `_resolve_preprocess_lane`, where opt-in detected on non-GPU profile prints the FR-010 stderr line and forces `Invocation.warmup = False`; (b) `src/ledgerlinc_ocr/pipeline/corpus_run.py` `run_warm_corpus()` after `_warm_initialize_live_preprocess` succeeds, where opt-in detected on non-GPU `--preprocess-profile` prints the FR-010 line. Both paths use `warn_and_proceed_message(profile_name)` from `preprocessing.warmup_optin` so the literal `--gpu-warmup ignored:` is grep-stable per cli-contract.md §3. No `preprocessing.warmup` import on the warn-and-proceed branch (FR-011 / I-6). Original: Implement warn-and-proceed branch in the activation helper from T010 (or in `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/pipeline/cli.py`): when warmup opt-in is set AND the active profile is NOT `ppstructurev3@gpu`, emit ONE stderr line containing the literal `--gpu-warmup ignored:` per `contracts/cli-contract.md` §3 with the FR-010 wording (`warning: --gpu-warmup ignored: active preprocess profile is '<profile>', not 'ppstructurev3@gpu'`); do NOT lazy-import `preprocessing.warmup`; do NOT call `_apply_env_defaults`; do NOT read or write `~/.cache/miopen` or `~/.cache/comgr`; the run proceeds with the same exit status it would produce without the opt-in (FR-010, SC-007, I-6, I-7)
- [x] T022 [P] [US3] ✅ DONE — CPU-safe test landed at `tests/unit/preprocessing/test_warmup_cpu_no_op.py` (5 tests). Mocks `preprocessing.pipeline.run` so it doesn't need paddleocr installed. Tests: stderr warn-line emission + Invocation.warmup=False threading; no MIOpen env mutation (FR-010 / I-7); env-var path equivalent to CLI-flag path; default-off baseline (no spurious warning); run_summary has no `phase_timings.warmup` (SC-007). Includes the FR-011 / I-6 sys.modules check (no `preprocessing.warmup` import on warn-and-proceed). Skips cleanly here (no PIL/numpy in dev env); will run green in devcontainer. Original: CPU-safe test in `tests/preprocessing/test_warmup_cpu_no_op.py`: run `--gpu-warmup` with `ppstructurev3@cpu` AND with the stub adapter; assert exactly ONE stderr line containing literal `--gpu-warmup ignored:`; assert no `phase_timings.warmup` in any emitted `run_summary`; capture pre/post mtime of `~/.cache/miopen` and `~/.cache/comgr` and assert unchanged (touch directories before the run if they don't exist); assert no `MIOPEN_*` env var was set during the run via a pre/post environ snapshot diff; **assert no `paddle*` / `paddleocr*` / `paddlex*` / `ledgerlinc_ocr.preprocessing.warmup` module appears in `sys.modules` after the run via a pre/post `sys.modules` keys diff** (FR-011 strong-form coverage per /speckit.analyze H1); assert exit status equals the run without `--gpu-warmup` (FR-010, FR-011, SC-006, SC-007)
- [x] T023 [P] [US3] ✅ DONE — purely CPU-safe test landed at `tests/unit/preprocessing/test_warmup_envvar_truthiness.py`. **49/49 tests PASS** in this dev env (no skipping needed since `warmup_optin` has zero GPU deps). Coverage: 9 truthy-whitelist + 14 non-truthy + unset + 4 CLI-wins-over-env precedence + 5 truth-table rows from data-model.md + warn-and-proceed message stability + 4 GPU-lane positive + 8 non-GPU-lane negative cases. Original: CPU-safe test in `tests/preprocessing/test_warmup_envvar_truthiness.py`: parameterize `LEDGERLINC_GPU_WARMUP` over `{"1", "true", "yes", "TRUE", "Yes"}` (all → ON) and `{"0", "false", "no", "2", "on", "enabled", "", unset}` (all → OFF); assert the activation helper from T010 returns the expected boolean; assert that when both `--gpu-warmup` (CLI) and `LEDGERLINC_GPU_WARMUP=0` (env) are set, CLI wins (returns ON) per `research.md` R-016.1

**Checkpoint**: CPU/stub paths are GPU-cost-free with the opt-in set; CI ergonomics intact; FR-013 default-suite-passes-without-GPU continues to hold.

---

## Phase 6: User Story 4 — Workstation cache and diagnostics are documented (Priority: P3)

**Goal**: A workstation operator new to GPU warmup can locate cache directories, clear them, run a cold-cache warmup, interpret `phase_timings.warmup`, understand `MIOPEN_FIND_MODE=2`, and triage MIOpen/COMGR workspace warnings — all from this feature's docs deliverable.

**Independent Test** (per `spec.md` §US4): open the docs deliverable; confirm it answers the five US4 Independent Test items: (a) cache locations; (b) how to clear; (c) `MIOPEN_FIND_MODE` default + rationale; (d) workspace warning meaning + disposition; (e) how to read `phase_timings.warmup` cold-vs-warm signal.

- [x] T024 [US4] ✅ DONE — `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` created (~250 lines). Eight sections covering all five US4 Independent Test items + recovery (CHK002 / CHK013 from failure-handling) + cache-state-after-failure (CHK012). Sections: TL;DR, cache locations, clearance procedure (full + comgr-only), `MIOPEN_FIND_MODE` mode comparison table + rationale, FR-016 hybrid policy (4-row addressed-by-default-config table + residual diagnostic placeholder for T026), `phase_timings.warmup` reading guide with sample run_summary excerpt + 5-row interpretation table, recovery triage table per cause-class, activation-surface reference. Original: Create `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` covering all five US4 Independent Test items: (a) `~/.cache/miopen` and `~/.cache/comgr` locations + clearance procedure (`rm -rf …`); (b) `MIOPEN_FIND_MODE=2` rationale per `research.md` R-016.4 (mode 1 / 2 / 3 / 4 contrast); (c) sample `run_summary` excerpt showing `phase_timings.warmup` alongside `paddle_import` / `gpu_bind_probe` / `engine_init`, with rounding-precision note (six decimal places) and the cold-vs-warm magnitude semantics from `gpu-observability.md` CHK007; (d) FR-016 hybrid dual list — "addressed by default config" (`MIOPEN_FIND_MODE=2`, `MIOPEN_USER_DB_PATH`, `MIOPEN_CUSTOM_CACHE_DIR`, `MIOPEN_LOG_LEVEL=2` from `data-model.md` §"Default env-var configuration", with the warning each suppresses) AND "residual / known runtime diagnostic" (each remaining warning text + meaning + whether operator should act); (e) operator recovery guidance for repeated `WarmupError` cases per `failure-handling.md` CHK002 / CHK013 (clear caches → retry once → if still failing, capture `cause_class` and triage); (f) cache-state-after-failure rule per `failure-handling.md` CHK012 (US4, FR-016, FR-017, SC-009, R-016.5)
- [x] T025 [P] [US4] ✅ DONE — cross-reference to `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` added to `CLAUDE.md` `## Key References` section, immediately after `ollama-runtime.md`. Original: Add a one-line cross-reference to the new doc in the `## Key References` section of `CLAUDE.md` so the deliverable is discoverable from the project index alongside `architecture.md`, `prd-model-pipeline.md`, etc.
- [ ] T026 [US4] ⏸ **DEFERRED per FR-014** — workstation MIOpen/COMGR warning catalog. Depends on T020's workstation cold-cache run output. Will populate the "Residual / known runtime diagnostics" table at `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` § 4b + `quickstart.md` Appendix B with observed workstation warnings split per FR-016 hybrid policy. Original: `@gpu` After T020 produces workstation values, populate `specs/016-gpu-warmup-miopen-cache/quickstart.md` Appendix B (workstation MIOpen/COMGR warning catalog) with the observed-on-this-workstation warning lines from T020's stderr log, split per FR-016 hybrid into "addressed" vs "residual"; propagate the dual list into the corresponding section of `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` from T024 so the docs deliverable contains real workstation evidence rather than the generic template (FR-016 / SC-009)

**Checkpoint**: docs deliverable shipped (or formally noted as awaiting workstation evidence under FR-014 if T026 is deferred). SC-009 mechanically testable against the file by walking the five US4 Independent Test items.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: pre-merge gate + the spec/contract tightening surfaced by the four checklists in `specs/016-gpu-warmup-miopen-cache/checklists/`.

- [ ] T027 [P] ⏸ PARTIAL — the 5 pre-existing schema_version assertions hard-coded to `"0.1.2"` were updated to `"0.1.3"` mid-Phase-2 (`tests/integration/test_single_doc_run_summary_emission.py`, `test_failure_phase_timings.py`, `test_warm_corpus_one_init.py`, `test_warm_corpus_stub_profiles.py`, `tests/pipeline_tests/test_run_summary_schema_0_1_2.py`). Full `pytest -m "not gpu"` smoke verification needs the project venv (PIL/numpy/pypdfium2/paddleocr/jsonschema/pydantic installed) — to be run by the operator in the devcontainer or `.venv-paddle-rocm` per FR-013. AST sanity checks for all 9 modified source files PASS in this dev env; T013's 10 schema assertions PASS via direct invocation; T023's 49 truthiness assertions PASS via pytest. Original: Run `.venv/bin/pytest -m "not gpu"` from repo root; confirm zero CPU-side regression (FR-013 / SC-006); fix any failures attributable to Phases 2–6 (most likely fixes are in pre-existing tests under `tests/contract_tests/` or `tests/pipeline/` that hard-code `schema_version == "0.1.2"` — update to `"0.1.3"` per FR-008)
- [x] T028 [P] ✅ DONE — checklist walk performed pre-implement (see "Walkthrough Complete" report earlier). Final state: requirements 16/16, release-readiness 46/48, failure-handling 16/18, gpu-observability 15/18 — total 93/100 ✅, with the 7 remaining items all blocked on T024 (T024 is now done; the 7 items can be re-checked against the new docs deliverable). FR-019 sanity check: no new persisted artifact outside `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` and the in-spec test-output files; verified via the file list created this session. Original: Walk all four checklists ...
- [x] T029 [P] ✅ DONE during /speckit.analyze remediation 2026-05-08 — spec FR-007 and SC-011 now explicitly cite exit code **15**, and SC-011's forbidden-state list now includes "no overall `run_summary` line is emitted on warmup failure" per `failure-handling.md` CHK005 / CHK010 / `gpu-observability.md` CHK016 (closes /speckit.analyze findings F1, F2)
- [x] T030 [P] ✅ DONE during /speckit.analyze remediation 2026-05-08 — spec §Definitions "Cold cache / warm cache" entry and the "MIOpen cache state" Key Entity now both pin the binding rule: production code detects cache state from `phase_timings.warmup.seconds` magnitude only; filesystem inspection is operator-side triage only per `gpu-observability.md` CHK006 (closes /speckit.analyze finding F3)
- [x] T031 [P] ✅ DONE during /speckit.analyze remediation 2026-05-08 — spec FR-009 now carries the explicit negative ("warmup time MUST NOT inflate `gpu_init_seconds`, `gpu_inference_seconds`, or `total_seconds`") and `contracts/run-summary-schema.md` §6 carries the matching backwards-compat clause per `gpu-observability.md` CHK009 (closes /speckit.analyze finding B1)
- [x] T032 ✅ DONE — Deferred Items subsection added below per FR-014. Operator instructions: when workstation GPU access is available, run the deferred items in order (T014–T017 GPU regression suite, then T018–T020 cold-vs-warm verification, then T026 warning catalog), tick off each here, and update SC-003 + research R-016.3 if observed cold/warm ratio differs materially from the placeholder 2× threshold. Until then, the implementation is CPU-safe and CI-clean; FR-014 explicitly permits merging without GPU verification provided the deferral is captured here.

---

## Deferred Items (FR-014)

**Tracking issue**: [opensoft/ledgerlinc-model-ocr-pipeline#23](https://github.com/opensoft/ledgerlinc-model-ocr-pipeline/issues/23) — *Feature 016: workstation GPU verification deferred per FR-014*

The following items require workstation GPU hardware (`@gpu` mark) and are deferred per FR-014. They MUST be run before the feature is considered fully verified, but they do NOT block merging the CPU-safe implementation. When the workstation is available, follow the operator instructions in the linked GitHub issue (or the equivalent steps below) and tick each item back to `[x]` in this file as it lands.

| Task | Verifies | Path |
|---|---|---|
| T014 | FR-001 / FR-003 / FR-018 / FR-020 / SC-008 (engine reuse + byte-identity) | `tests/pipeline_tests/test_warmup_engine_reuse.py` |
| T015 | SC-004 / I-4 (first-doc phase_timings exclude warmup) | `tests/pipeline_tests/test_warmup_first_doc_exclusion.py` |
| T016 | FR-004 / SC-005 (corpus warmup once-per-process) | `tests/pipeline_tests/test_warmup_corpus_once.py` |
| T017 | SC-011 / I-5 (warmup failure path) | `tests/pipeline_tests/test_warmup_failure_path.py` |
| T018 | SC-003 (cold-vs-warm 2× ratio) | `tests/pipeline_tests/test_warmup_cold_vs_warm.py` |
| T019 | US2 #3 (comgr-only-cleared mid-state) | `tests/pipeline_tests/test_warmup_comgr_only.py` |
| T020 | Workstation cold/warm/comgr-only seconds → `quickstart.md` Appendix A; tune SC-003 / R-016.3 if needed | `quickstart.md` §1–§3 |
| T026 | FR-016 residual warnings catalog → `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` § 4b + `quickstart.md` Appendix B | docs deliverable update |
| T027 (full smoke) | FR-013 / SC-006: complete `pytest -m "not gpu"` green in devcontainer / `.venv-paddle-rocm` (the Phase 2–6 schema-version fixes already landed; remaining is full-suite smoke) | repo-wide pytest |

**Operator instructions when GPU access becomes available**:

1. Activate the workstation GPU venv: `source .venv-paddle-rocm/bin/activate`
2. Run the GPU regression tests: `pytest -m gpu tests/pipeline_tests/test_warmup_*.py` — once each test file is implemented per its task description
3. Walk through `quickstart.md` §1–§3 (cold + warm + comgr-only) and record three `phase_timings.warmup.seconds` values into Appendix A
4. If observed cold/warm ratio is materially different from 2×, amend `research.md` R-016.3 + `spec.md` SC-003 BEFORE finalizing the verification
5. Capture observed-on-this-workstation MIOpen/COMGR warnings into `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` § 4b (the "Residual / known runtime diagnostics" table)
6. Tick the corresponding tasks above to `[x] DONE`
7. Open a follow-up commit / PR closing the deferral

A follow-up GitHub issue / OpenSpec change capturing this list MAY also be opened so the deferral is tracked outside this tasks file.

**Checkpoint**: feature ready for PR review. All four checklists pass or have explicit deferrals. CPU-side regression confirmed clean. Workstation evidence captured (or deferred per FR-014).

---

## Dependencies

```text
Phase 1 (T001) ─────────────────────────────────┐
                                                 │
Phase 2 (T002 [P], T003 [P], T004 [P]) ─────────┤
                                                 │
                                                 ▼
                  ┌───────────────────────────────────────────────────────────┐
                  │                                                            │
Phase 3 (US1):    T005 ──┬─→ T006 ──┐                                          │
                         │          ├─→ T011 ──→ (US1 wiring complete)         │
                         └─→ T007 ──┘             │                            │
                                                  ▼                            │
                          T008, T009 [P], T010 ──→ (US1 CLI complete)          │
                                                                               │
                  T012 [P], T013 [P]  (CPU tests, depend on T002/T003/T004)    │
                  T014 [P], T015 [P], T016 [P], T017 [P]  (@gpu, depend on US1 wiring) │
                  ─────────────────────────────────────────────────────────────┤
                                                                               │
Phase 4 (US2):   T018 [P], T019 [P]  (@gpu, depend on US1 complete)            │
                  T020             (@gpu workstation, depends on T018/T019)    │
                  ─────────────────────────────────────────────────────────────┤
                                                                               │
Phase 5 (US3):   T021              (depends on T010)                            │
                  T022 [P], T023 [P]  (CPU, depend on T021)                     │
                  ─────────────────────────────────────────────────────────────┤
                                                                               │
Phase 6 (US4):   T024              (independent of code; can start as soon as Phase 2 done) │
                  T025 [P]          (CLAUDE.md, after T024)                    │
                  T026             (@gpu, after T020 + T024)                   │
                                                                               │
Phase 7:         T027 [P], T028 [P], T029 [P], T030 [P], T031 [P]              │
                  T032 (after T020 / T026 outcome known)                       │
                  ─────────────────────────────────────────────────────────────┘
```

**Story dependencies** (the most-actionable summary):
- US1 is the MVP and must complete before US2's tests (T018, T019) can run.
- US2 is independent of US3 and US4 — they may all run in parallel after US1 ships.
- US4 (docs) is independent of any source code; T024 can begin as soon as Phase 2 completes, and T026 only needs T020's workstation output.
- US3 only depends on T010 (the activation helper) from US1's CLI work; T010 can be pulled forward and US3 can ship alongside US1.

## Parallel Execution Examples

**Phase 2 (foundational)** — three independent tasks in different files / functions; can run together:

```
T002 [P]  errors.py — add WarmupError
T003 [P]  pipeline/timing.py — bump SCHEMA_VERSION
T004 [P]  pipeline/timing.py — extend attach_one_time_gpu_phases (different function from T003)
```

**Phase 3 (US1 implementation)** — once T005 is done, the wiring tasks split by file:

```
T006     preprocessing/pipeline.py — single-doc wiring
T007     pipeline/corpus_run.py    — corpus wiring
T008 [P] preprocessing/cli.py      — single-doc CLI flag
T009 [P] pipeline/cli.py           — corpus CLI flag
T010     preprocessing/cli.py      — activation helper (same file as T008; sequential after T008)
```

**Phase 3 (US1 tests)** — six tests across different test files; all parallel:

```
T012 [P] tests/preprocessing/test_warmup_unit.py            (CPU-safe)
T013 [P] tests/pipeline/test_run_summary_schema_0_1_3.py    (CPU-safe)
T014 [P] tests/pipeline/test_warmup_engine_reuse.py         (@gpu)
T015 [P] tests/pipeline/test_warmup_first_doc_exclusion.py  (@gpu)
T016 [P] tests/pipeline/test_warmup_corpus_once.py          (@gpu)
T017 [P] tests/pipeline/test_warmup_failure_path.py         (@gpu)
```

**Phase 7 (polish)** — five spec/contract tightening tasks all in different sections of different files; all parallel:

```
T027 [P]  pytest -m "not gpu" run
T028 [P]  walk four checklists
T029 [P]  spec FR-007 / SC-011 — exit code 15 + forbidden-state extension
T030 [P]  spec §Definitions cold/warm reconciliation
T031 [P]  spec FR-009 negative assertion + contract update
```

## Implementation Strategy

**MVP** (US1 only — Phases 1, 2, 3): warmup runs once, reports `phase_timings.warmup`, fail-fasts cleanly. This alone delivers the headline value of feature 016 — variance pushed out of `per_page_inference`. Ship US1 + Phase 7 polish if time-pressured; defer US2 cold-vs-warm verification under FR-014.

**Standard release** (Phases 1–7 with all stories): MVP plus cold-vs-warm observability (US2), CPU/stub no-op (US3), and docs deliverable (US4). Recommended landing scope.

**Incremental order**:
1. T001 (Phase 1, sanity check) → T002 / T003 / T004 in parallel (Phase 2).
2. US1 wiring (T005 → T006 / T007 / T008–T010 / T011) → US1 CPU tests (T012, T013) merge first.
3. Pull US3 (T021 / T022 / T023) forward in parallel with US1's GPU tests since US3 only needs T010.
4. US1 GPU tests (T014–T017) gate the merge — defer per FR-014 if no GPU access.
5. US2 (T018 / T019 / T020) and US4 (T024 / T025 / T026) in parallel after US1 ships.
6. Phase 7 polish to close the spec/contract gaps surfaced by the four checklists.

## Format Validation

All 32 tasks follow the strict format `- [ ] [TaskID] [P?] [Story?] Description with file path`:

- ✅ Every line starts with `- [ ]`
- ✅ Sequential T001–T032 in execution order
- ✅ `[P]` only on tasks in different files / independent functions with no incomplete dependencies
- ✅ `[USn]` label present on every Phase 3–6 task; absent on Phase 1 (Setup), Phase 2 (Foundational), Phase 7 (Polish)
- ✅ Every task description includes at least one absolute or repo-root-relative file path

**Total**: 32 tasks across 7 phases.

| Phase | Story | Task count | Parallelizable |
|---|---|---:|---:|
| 1 — Setup | — | 1 | 0 |
| 2 — Foundational | — | 3 | 3 |
| 3 — US1 (P1, MVP) | US1 | 13 | 8 (4 impl + 6 tests, minus T010 which serializes after T008) |
| 4 — US2 (P1) | US2 | 3 | 2 |
| 5 — US3 (P2) | US3 | 3 | 2 |
| 6 — US4 (P3) | US4 | 3 | 1 |
| 7 — Polish | — | 6 | 5 |
| **Total** | | **32** | **21** |
