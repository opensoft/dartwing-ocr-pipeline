# Research: GPU Warmup And MIOpen Cache Stabilization

**Feature**: 016-gpu-warmup-miopen-cache
**Date**: 2026-05-08

This document resolves the implementation-level decisions the spec explicitly deferred to `/speckit.plan` (Assumptions section: warmup activation mechanism, warmup-pass input fixture, SC-003 cold-vs-warm threshold tuning, `MIOPEN_FIND_MODE` default value, FR-015 amendment hook), the FR-016 hybrid workspace-warning policy concretization (per /speckit.clarify Q3), plus the three internal architecture choices the implementation has to make (failure-mode wiring, warmup module location, run_summary emission surface). One decision per section, in the standard `Decision / Rationale / Alternatives considered` format.

## R-016.1: Activation mechanism

**Decision**: Add a `--gpu-warmup` boolean CLI flag to the existing `python -m ledgerlinc_ocr.preprocessing` entry point and to `python -m ledgerlinc_ocr.pipeline` (corpus mode). The same opt-in is also accepted via the env var `LEDGERLINC_GPU_WARMUP=1` (any of `1`, `true`, `yes` — case-insensitive — counts as set; everything else, including unset, counts as unset). When both surfaces are present, the CLI flag wins. The opt-in is **off by default** (FR-002) and **orthogonal** to `--preprocess-profile` (Assumptions): a CPU/stub run silently no-ops the env-var case but emits a one-line stderr warning either way per FR-010 (per /speckit.clarify Q1: warn-and-proceed).

**Rationale**:
- A CLI flag matches feature 014's `--preprocess-profile` precedent on the same entry points; operators discover it in `--help` next to the profile selector and the existing logging / preflight knobs.
- An env-var fallback supports two real workflows: shared CI pipelines (set the env once for the GPU job stage), and shell-loop scripts that toggle warmup across runs without rewriting the command (e.g., the cold-vs-warm verification in SC-003). Without an env-var surface, those scripts have to splice the flag in conditionally, which is error-prone.
- "CLI wins over env var" is the standard precedence and is consistent with how `LOG_LEVEL` and similar env vars compose with their flag counterparts elsewhere in this codebase.
- Booleans (no `--gpu-warmup=auto` mode, no per-N-passes count) are deliberate: FR-001 / FR-004 say *exactly one* warmup pass per process. Adding a count parameter would invite a future drift toward "let the user pick", which contradicts the FR.

**Alternatives considered**:
- **Env var only**. Rejected: discoverability is poor (`--help` doesn't show env vars) and feature 014's flag-based precedent would be broken.
- **Profile suffix** (`ppstructurev3@gpu+warmup`). Rejected: violates the "orthogonal to `--preprocess-profile`" assumption and would multiply the profile namespace combinatorially with future opt-ins.
- **Auto-warmup whenever `ppstructurev3@gpu` is selected**. Rejected: FR-002 explicitly requires opt-in default-off behavior so the existing data-driven latency analysis from feature 015 keeps working without warmup unless the operator asks for it.
- **Make it a count** (`--gpu-warmup-passes N`). Rejected: contradicts FR-001 / FR-004's exactly-one rule. If we ever need >1 pass for multi-shape coverage, that's a follow-up feature with its own clarify pass.

## R-016.2: Warmup-pass input fixture

**Decision**: The warmup pass invokes `engine.predict(np_img)` against **page 1 of `tests/stage1_vendor_identity/inv_001_easy/source.pdf`**, rasterized through the existing `preprocessing.rasterize.rasterize_page(...)` path at the same DPI used by the preprocess profile (default 300 DPI for `ppstructurev3@gpu`, matching feature 003). The fixture is loaded **once per process** at warmup time; `preprocessing/warmup.py` owns the path and the loader. If the fixture is unreadable for any reason (missing file, IO error, pypdfium2 error), the warmup function raises `WarmupError` with cause class `FixtureLoadError` — fail-fast per FR-007.

**Rationale**:
- "Same input shape, same number of pages, same code path the timed documents will exercise" (FR-005) is satisfied: the fixture rasterizes through the same path the corpus does, hits the same V3 layout/OCR sub-models, and produces the same `engine.predict` call signature.
- Reusing an existing committed corpus fixture (rather than synthesizing a blank or random image) keeps determinism cheap — the fixture is tracked in git, its sha256 is stable, and the `inv_001_easy` baseline is already covered by feature 015's GPU regression.
- One-page is intentional: warming a single canonical layout is enough to populate MIOpen kernel-selection caches for all kernels the V3 backbone uses (the kernels are shape-driven, not content-driven; cf. SC-003 cold-vs-warm validation). Multi-page warmup adds time without measurably more cache coverage on this stage 1 corpus.
- Loading the fixture from disk inside `warmup.py` (rather than passing a numpy array in from the runner) keeps the warmup contract self-contained: the runner just calls `run_warmup(engine)` and doesn't have to know about fixture paths.

**Alternatives considered**:
- **Deterministic synthetic image** (fixed-size white numpy array, e.g., `np.full((3300, 2550, 3), 255, dtype=np.uint8)`). Rejected for stage 1: an all-white image short-circuits PP-OCRv5 to a near-empty result that does not exercise the OCR + layout kernels we want to warm. A synthetic image with text (PIL-rendered) is a possibility but adds rendering nondeterminism risk.
- **Smallest fixture in the corpus** (a different `inv_NNN`). Rejected: `inv_001_easy` is already the canonical "happy-path simple invoice" used as the smoke test elsewhere; reusing it minimizes test flakiness and lets us reuse the existing baseline.
- **All 20 corpus fixtures, one per shape variation**. Rejected: adds tens of seconds to every warmup-enabled run for marginal kernel-cache coverage, defeating the "pay warmup cost up front *once*" goal.
- **An in-memory fixture bundled via `importlib.resources`**. Considered but rejected: bundling a binary fixture inside the package complicates licensing and weights against the existing convention of letting the corpus live under `tests/stage1_vendor_identity/`.

## R-016.3: SC-003 cold-vs-warm 2× threshold

**Decision**: The SC-003 threshold lands as **`cold_seconds >= 2 * warm_seconds`** (the spec placeholder), with a one-time tuning hook: the workstation operator running the cold-vs-warm verification records both seconds values into `quickstart.md` Appendix A at landing time. If both observed runs satisfy the placeholder, no spec amendment is needed. If the observed cold/warm ratio is consistently below 2× (e.g., MIOpen find-mode 2 + the default config end up too cache-warm-from-the-start) or consistently above (e.g., 10×+ on first cold run), the threshold is amended in this `research.md` and the spec's SC-003 line is updated under FR-014's "tracked as a follow-up issue/task" deferral path before merge.

**Rationale**:
- The 2× threshold is pessimistic enough to detect a meaningful difference (kernel selection visibly compiles in mode-2 fast-find on first run; second run hits the kernel database) and lax enough that small-fixture variance doesn't trip it.
- Pinning the threshold *now* (before any workstation evidence) would either bake in a too-tight bound (false-failure on jitter) or a too-loose bound (no signal). The tune-on-landing approach matches feature 015's pattern of "ship the slice; record observed numbers in quickstart; tune the gate only when we have real data".
- The verification workflow is captured end-to-end in quickstart.md so the next operator (or a follow-up run after a ROCm bump) can repeat it deterministically.

**Alternatives considered**:
- **Pin a tighter threshold (e.g., 5×)**. Rejected without evidence: there is no public ROCm/MIOpen reference for "expected first-run vs cached-run kernel-selection cost on gfx1151 + this workload", and tightening the gate without data risks landing an over-strict criterion.
- **Pin a looser threshold (e.g., 1.2×)**. Rejected: too close to noise floor; would let a regression where MIOpen *isn't* hitting the cache slip past.
- **Replace the ratio with an absolute floor** (e.g., warm < 5 s). Rejected: absolute floors don't survive ROCm/driver upgrades; the ratio is more durable.

## R-016.4: `MIOPEN_FIND_MODE` default value

**Decision**: This feature ships **`MIOPEN_FIND_MODE=2`** (Fast / "exhaustive search disabled, fast heuristic + cached lookup") as the default for warmup-enabled GPU runs. The variable is set inside `preprocessing/warmup.py` (and only there) at the start of `run_warmup()` if the env var is unset; if the operator has explicitly exported a different value, this feature does not override it (operator intent wins). The variable is **not** unset after warmup — it remains in effect for the rest of the process, which is the intended behavior since per-doc inferences should also benefit from fast-find.

**Rationale**:
- Mode 2 (Fast) is the standard MIOpen recommendation for production workloads where one-shot exhaustive search (mode 1) is too expensive and pure cache-only (mode 4) errors out on cache-miss kernels. Mode 3 (hybrid) trades correctness against a larger first-run cost than mode 2 for marginal long-run benefit on this stage 1 workload.
- Setting the env var in `warmup.py` (rather than in the CLI or the runner) keeps the side effect localized: CPU/stub paths cannot accidentally pick it up, satisfying FR-010 / FR-011's CPU-isolation requirement.
- Respecting an operator-set value is consistent with how `OLLAMA_BASE_URL` and `LOG_LEVEL` work elsewhere in this codebase: defaults are forgiving overrides, not lockouts.

**Alternatives considered**:
- **Mode 1 (Full search) as default**. Rejected: every cold-cache run takes minutes to populate. The whole point of feature 016 is to make warmup *fast* so it can run inline; mode 1 makes warmup itself the bottleneck.
- **Mode 4 (Cache-only) as default**. Rejected: errors out on the first cold run and any post-driver-update run, which contradicts FR-007's expectation that warmup completes deterministically.
- **Leave the variable untouched**. Rejected: MIOpen's own default behavior across versions is not stable; pinning mode 2 makes "what will this run do" answerable from spec + research alone.
- **Set it codebase-wide for every run** (CPU and GPU). Rejected: violates FR-011 (CPU/stub paths must not import or trigger MIOpen-specific paths).

If workstation evidence at landing time shows that mode 2 is materially worse than another mode for this gfx1151 + V3 workload, FR-015's amendment hook applies: update this section + spec FR-015 + quickstart before merge.

## R-016.5: Workspace-warning suppression default config (FR-016 hybrid)

**Decision**: This feature ships the following default env-var configuration, applied inside `preprocessing/warmup.py` only when the GPU warmup path is taken (so CPU/stub paths are unaffected per FR-011), and only when the operator has not already set the variable:

| Default | Purpose |
|---|---|
| `MIOPEN_FIND_MODE=2` | Fast find (R-016.4) |
| `MIOPEN_USER_DB_PATH=$HOME/.cache/miopen` | Pin user kernel DB to a stable, operator-clearable location (suppresses the "MIOpen could not determine user db path" workspace warning observed during feature 015 verification) |
| `MIOPEN_CUSTOM_CACHE_DIR=$HOME/.cache/miopen` | Pin compile cache to the same directory (suppresses the "custom cache dir not set" warning) |
| `MIOPEN_LOG_LEVEL=2` | Errors + warnings only (default is verbose info); does NOT suppress the warnings catalogued below — only quiets the high-volume per-kernel info traces that polluted feature 015 stderr logs |

The actually-observed-on-this-workstation warnings, split per FR-016 (per /speckit.clarify Q3) into "addressed by default config above" vs "residual / known diagnostic", are catalogued in `docs/stage1-vendor-identity/gpu-warmup-and-cache.md`. The split is finalized at landing time after one cold-cache + one warm-cache verification run; the doc deliverable MUST contain both lists with their meaning + operator guidance.

**Rationale**:
- The four env vars above are the documented MIOpen knobs that have a known, safe-to-set effect on warning emission and cache directory layout. They do not change observable kernel-selection behavior — which keeps the SC-008 byte-identity-of-`preprocess_output.json` guarantee intact.
- Pinning MIOpen's user DB and custom cache dir to `$HOME/.cache/miopen` is what MIOpen would use anyway by default on Linux; explicitly setting the path means MIOpen does not need to compute it from incomplete HSA/runtime hints, which is what produces the workspace-warning chatter. **COMGR's cache directory (`$HOME/.cache/comgr`) is a separate OS-level convention managed by the AMD COMGR library and is NOT controlled by any of the env vars this feature sets** — operators who need a non-default COMGR path use whatever knob the local ROCm/COMGR build exposes (typically `XDG_CACHE_HOME` or distribution-specific configuration). Both directories are operator-clearable for cold-cache verification.
- "Don't override an operator-set value" is consistent with R-016.4 and with the rest of the codebase's env-var-with-overrides convention.
- Splitting the residual warnings into a documented diagnostic list (with operator guidance) per FR-016(b) avoids the trap of "these warnings are scary but actually fine, sorry" — the docs deliverable lists each one with what it means and whether the operator should act.

**Alternatives considered**:
- **Eliminate by config only — keep adding env vars until silent**. Rejected: not all MIOpen runtime warnings have a known-safe configuration knob. Forcing silence by, e.g., setting `MIOPEN_LOG_LEVEL=1` (errors only) hides legitimate kernel-init failures and contradicts the "silent suppression NOT acceptable" rule in FR-016.
- **Document everything, configure nothing**. Rejected: the four env vars above are the documented standard configuration for production MIOpen — leaving them unset would be operationally substandard. The hybrid is honest about what's defaulted vs what remains.
- **Apply the env vars at process start (not in warmup.py)**. Rejected: contaminates CPU/stub paths and violates FR-011.

## R-016.6: Failure-mode wiring (`WarmupError`)

**Decision**: A new `WarmupError(message: str, cause_class: str, cause_module: str)` exception lives in `preprocessing/errors.py`, mirroring the `EngineInitError` pattern used by feature 010/014. `preprocessing/warmup.run_warmup(engine)` catches any exception raised by `engine.predict(...)` (or by the fixture loader) and re-raises as `WarmupError` with the cause's class and module preserved. Both call sites (single-doc `preprocessing/pipeline.py` and corpus `pipeline/corpus_run.py`) catch `WarmupError` at the same boundary they already catch `GpuPrerequisiteError`: print `error: warmup failed: <cause-class>: <message>` to stderr, exit non-zero (exit code **15**, immediately after feature 014's preflight 10–14 range), and emit no `phase_timings.warmup`, no per-document `run_summary` entry for any document that would have been timed after the failed warmup, and no `preprocess_output.json` for any such document. The run does NOT silently downgrade (FR-007 / SC-011).

**Rationale**:
- Reusing the established `EngineInitError` shape keeps error-handling code consistent across the preprocessing surface.
- Exit code 15 fits naturally after feature 014's 10–14 GPU-preflight exit codes and the success-0 / generic-1 baseline. It is **not** a preflight code (preflight already passed by the time warmup runs) — it's a new "GPU runtime fail-fast" code, but operationally it has the same shape as a preflight failure.
- Failing at the same boundary the preflight failure path uses means the existing `_warm_init_failure_phase_timings` plumbing (which already attaches whatever `phase_timings` were captured before failure) extends naturally to warmup-time failures: paddle_import / gpu_bind_probe / engine_init are all captured at warmup-failure time; only `warmup` itself is omitted.
- Suppressing run_summary emission entirely on warmup failure (rather than emitting a partial one with `documents_total = 0`) matches SC-011's text: "no per-document `run_summary` entry is emitted for any document that would have been timed after the failed warmup". An overall run_summary header without any per-document entries is more confusing than emitting nothing.

**Alternatives considered**:
- **Subclass `GpuPrerequisiteError`**. Rejected: warmup is not a prerequisite check; it is a runtime invocation. Conflating the two would muddy SC-011's distinction between the preflight fail-fast surface and the warmup fail-fast surface.
- **Re-raise the underlying exception unchanged**. Rejected: callers would have to know about every paddle/MIOpen/COMGR exception type. The wrapper preserves the cause class for diagnostics while giving callers a single type to handle.
- **Emit a partial run_summary with `documents_total = 0` on warmup failure**. Rejected: SC-011 says "no per-document run_summary entry"; a header-only run_summary is a degenerate shape consumers don't currently parse.
- **Allow silent fallback to a no-warmup run**. Rejected: explicitly forbidden by FR-007 and SC-011 ("MUST NOT silently downgrade").

## R-016.7: Warmup module location (`preprocessing/warmup.py`)

**Decision**: The warmup logic lives in a new module `src/ledgerlinc_ocr/preprocessing/warmup.py`. The module exposes:

```python
def run_warmup(engine: Any, *, fixture_path: Path | None = None) -> WarmupResult: ...
```

…where `WarmupResult` is a frozen dataclass `{seconds: float, fixture_sha256: str}` (the sha256 is for diagnostics in quickstart.md and for the cold-vs-warm regression test, not for the run_summary). The module is imported only on the GPU code path (the import line lives inside the `if device == "gpu" and warmup_opt_in:` branch in `preprocessing/pipeline.py` and `pipeline/corpus_run.py`) so a host without Paddle/ROCm can `import ledgerlinc_ocr.preprocessing` without indirectly pulling MIOpen-specific code (FR-011).

**Rationale**:
- A new module keeps warmup mechanics out of `ocr.py` (which is already large and busy with V3 inference plumbing) and out of `preflight.py` (which is preflight, not runtime).
- The narrow public API (`run_warmup` + `WarmupResult` + `WarmupError`) is easy to mock in `test_warmup_unit.py` (CPU-safe) and easy to stub for the CPU/stub no-op tests.
- Lazy import on the GPU branch means `from ledgerlinc_ocr.preprocessing import warmup` never fires on CPU/stub paths, satisfying FR-011's "MUST NOT import GPU-only modules" rule.

**Alternatives considered**:
- **Put `run_warmup` in `ocr.py`** as a sibling of `_get_engine`. Rejected: bloats `ocr.py` further and entangles warmup with V3 inference helpers that have nothing to do with warmup.
- **Put it in `preflight.py`**. Rejected: preflight is the once-per-process classification step; warmup is a once-per-process runtime invocation. Putting them together would obscure the distinct lifecycles.
- **Make `run_warmup` a method on `RunSummary` or a stage adapter**. Rejected: warmup is not a stage; it's pre-stage. A free function in a dedicated module is the simplest match.

## R-016.8: Run_summary emission surface (extend vs sibling)

**Decision**: Extend the existing `attach_one_time_gpu_phases(record, readout)` helper in `pipeline/timing.py` with a new keyword-only parameter `warmup_seconds: float | None = None`. When provided non-None, it appends `record["phase_timings"]["warmup"] = {"seconds": warmup_seconds}` alongside `paddle_import` / `gpu_bind_probe` / `engine_init`. When None (default — warmup not run, or warmup ran but failed before completing), the key is omitted. The existing call sites in `runner.py` and `corpus_run.py` pass either the captured warmup seconds or None depending on whether `run_warmup` succeeded.

**Rationale**:
- One helper, one source of truth for "which keys go on the first successful per-document entry". A sibling `attach_warmup_phase` would split the "first-doc one-time phases" responsibility across two functions and make it harder to reason about ordering or absence.
- Keyword-only with a default of None is additive: every existing call site continues to work without modification; only the wiring points that opted into warmup pass the new kwarg.
- The "seconds" type is `float`, six-decimal rounded by the caller (`round(seconds, 6)`), matching the rounding convention already used throughout `pipeline/timing.py`.

**Alternatives considered**:
- **Add a sibling `attach_warmup_phase(record, warmup_seconds)`**. Rejected for the consolidation reason above.
- **Pass a structured `WarmupResult` rather than a float**. Rejected: the run_summary contract is `{seconds: <float>}` only (FR-006 / FR-007 / Definitions). The fixture sha256 is internal diagnostic data, not part of the schema.
- **Always emit `phase_timings.warmup`, with `seconds: 0.0` when warmup didn't run**. Rejected: feature 015 FR-016 says "absent phases are omitted, not zeroed" — and FR-007 reaffirms this: failed warmup means *no* `phase_timings.warmup` key.

## R-016.9: Schema_version bump scope (per /speckit.clarify Q2)

**Decision**: This feature ships a single codebase-level patch bump to `pipeline/timing.py`'s `SCHEMA_VERSION`: **`"0.1.2"` → `"0.1.3"`**. Every run of the new binary emits `schema_version: "0.1.3"`, regardless of whether the warmup opt-in was set, whether warmup ran, or whether it succeeded. The bumped 0.1.3 schema permits a `warmup` key under `phase_timings` (additive, optional). The `warmup` key is **absent** in the emitted run_summary unless `run_warmup` actually completed successfully (FR-007 / FR-016 "absent phases are omitted, not zeroed").

**Rationale**:
- This decision is recorded in /speckit.clarify session 2026-05-08 Q2 (codebase-level over per-run conditional). Captured here so the bump shows up in research review and so contract tests (`test_run_summary_schema_0_1_3.py`) can assert "schema_version is exactly '0.1.3' on every run" without relying on the spec wording alone.
- The bumped schema's "warmup is optional" stance composes cleanly with feature 015's already-optional `paddle_import` / `gpu_bind_probe` / `engine_init` / `per_page_inference` keys: every additive 0.1.x bump has been "permit a new optional key". 0.1.3 is the third such bump (014's 0.1.0→0.1.1, 015's 0.1.1→0.1.2, 016's 0.1.2→0.1.3).
- One bump per feature is the established pattern; bumping minor (0.2.0) would be a breaking signal not warranted here.

**Alternatives considered**:
- **Per-run conditional bump** (emit 0.1.2 when warmup didn't run, 0.1.3 only when it did). Rejected by /speckit.clarify Q2.
- **Bump twice in one feature** (e.g., 0.1.2 → 0.1.4). Rejected: no second additive change in this feature; one new optional key = one patch bump.
- **Bump minor (0.2.0)**. Rejected: this is purely additive, consumers built against 0.1.2 continue to read 0.1.3 output without changes.

## R-016.10: Corpus-run wiring point and one-time-per-process guarantee

**Decision**: In `pipeline/corpus_run.py`, the warmup invocation lives between the existing `_warm_initialize_live_preprocess(...)` call (which adopts the engine via `ocr._adopt_engine`) and the per-document loop's first iteration. Concretely (current line numbers reference the existing `corpus_run.py`): immediately after the `if warm_init_failure is not None:` block at L271–278 and before the `for entry in documents:` loop at L285. Single-doc path in `pipeline/runner.py` mirrors this: warmup runs after the equivalent engine-adoption step succeeds and before the first `measure_total(timing)` invocation. A module-level `_WARMUP_RAN: bool = False` flag in `preprocessing/warmup.py` enforces the once-per-process guarantee (FR-004); subsequent calls return the cached `WarmupResult` without re-invoking `engine.predict` and without re-applying env defaults.

**Rationale**:
- Wiring at this exact point (post-adopt, pre-first-doc) satisfies FR-001 / FR-003: the engine exists, no second engine is constructed, and no document timing has started yet.
- The module-level flag is the same pattern feature 015 uses for `_PADDLE_SEEDED` and the `_ENGINE_DEVICE` singleton — a process-scoped guard with no test fixtures to coordinate.
- Returning the cached `WarmupResult` on a (defensive) second call lets us preserve the reported `phase_timings.warmup.seconds` value if some unexpected control-flow path ever invokes `run_warmup` twice. The expected control flow invokes it exactly once.

**Alternatives considered**:
- **Wire warmup inside `_warm_initialize_live_preprocess`**. Rejected: that helper is shared by warmup-disabled runs; conditioning inside it would fan the opt-in detection out across modules.
- **Wire warmup inside `_get_engine`** (run a warmup pass on the first engine retrieval after adoption). Rejected: makes `_get_engine` non-idempotent on first call and entangles inference plumbing with opt-in detection.
- **No process-level flag; rely on caller discipline**. Rejected: defensive flag is nearly free and protects against future refactors that accidentally double-invoke `run_warmup` (e.g., a re-entrant test fixture).
