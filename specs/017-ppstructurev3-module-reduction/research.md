# Research: PPStructureV3 Module And Model Reduction

**Feature**: 017-ppstructurev3-module-reduction
**Date**: 2026-05-09

This document resolves the implementation-level decisions the spec deferred to `/speckit.plan` (Assumptions section: activation flag names, exact CPU-default identifier strings, lighter variant selection, corpus subset, audit instrumentation approach), the four `[Gap]`-marked items from the four release-gate checklists that this layer is responsible for, plus the internal architecture choices the implementation has to make (preset registry shape, error wiring, schema_version bump, quality-gate metric extraction). One decision per section, in the standard `Decision / Rationale / Alternatives considered` format.

## R-017.1: Activation mechanism for both new switches

**Decision**: Add two CLI flags to BOTH the existing `python -m ledgerlinc_ocr.preprocessing` entry point and `python -m ledgerlinc_ocr.pipeline` (corpus mode):

- `--module-set <id>` (string; default `cpu-default` on the CPU profile, default `legacy` on the GPU profile)
- `--det-rec-variant <id>` (string; default `cpu-default` on the CPU profile, default `legacy` on the GPU profile)

Each flag has an env-var fallback:

- `LEDGERLINC_MODULE_SET=<id>` (CLI flag wins when both are set)
- `LEDGERLINC_DET_REC_VARIANT=<id>` (CLI flag wins when both are set)

**Env-var literal-value handling**: the env-var value is passed verbatim to `resolve_module_set` / `resolve_det_rec_variant` — no `.strip()`, no case normalization, no whitespace trimming. A trailing newline, surrounding whitespace, or a mixed-case value (e.g., `Reduced-V1`) results in `UnknownPresetError` → exit code 16. This is intentional: identifier values are case-sensitive lowercase by codebase convention (`ppstructurev3@gpu`, etc.); a forgiving normalization here would mask typos. The same handling applies to the CLI flag — `argparse` does not normalize string values either.

Both flags are **off-by-default** in the sense that the empty / unset case selects the active profile's default identifier. They are **orthogonal** to `--preprocess-profile` and `--gpu-warmup` (an operator can combine `--preprocess-profile=ppstructurev3@gpu --gpu-warmup --module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile` in a single invocation).

When either flag is set on `ppstructurev3@cpu` or any stub adapter, the CLI emits a single stderr warning containing the literal `--module-set ignored:` (or `--det-rec-variant ignored:`) and proceeds with the active profile's default — warn-and-proceed, not silent-ignore and not rejection (FR-013, mirroring feature 016 FR-010). Selecting an unknown identifier value (e.g., `--module-set reduced-v99` or `--det-rec-variant ppocrv9_imaginary`) fails fast with exit code 16 and a clear stderr message naming the valid values for that axis (R-017.12).

**Rationale**:
- The CLI-flag-with-env-var-fallback shape matches feature 014's `--preprocess-profile` and feature 016's `--gpu-warmup` precedents on the same entry points; operators discover the flags in `--help` next to the existing knobs.
- Two separate flags (rather than a single combined string like `--gpu-config legacy:legacy`) is the natural shape for two separate top-level run_summary fields agreed under /speckit.clarify Q2 (`module_set_id` + `det_rec_variant_id`). It also makes filter-by-axis trivial in shell loops (e.g., bench every det/rec variant against the legacy module set).
- "CLI wins over env var" is the standard precedence and matches feature 016 R-016.1.
- Strings (not enums) keep the identifier extensible without contract churn — matches the human-readable-not-hash requirement in FR-008.

**Alternatives considered**:
- **Single combined flag** (`--gpu-config legacy:legacy`). Rejected: contradicts /speckit.clarify Q2 (two separate top-level fields). Combined string requires parse-on-read everywhere it's grepped.
- **Profile suffix** (`ppstructurev3@gpu+reduced+ppocrv5-mobile`). Rejected: violates the "orthogonal to `--preprocess-profile`" assumption and would multiply the profile namespace combinatorially.
- **Env vars only**. Rejected: discoverability is poor (`--help` does not show env vars) and would break the feature 014 / 016 flag-based precedent.
- **Per-sub-module toggle flags** (`--no-table --no-formula …`). Rejected: contradicts /speckit.clarify Q4 (named presets only, closed vocabulary on `module_set_id`).

## R-017.2: Closed `module_set_id` vocabulary at landing

**Decision**: Exactly four valid values at landing time:

| Value | Profile | Meaning |
|---|---|---|
| `legacy` | `ppstructurev3@gpu` only | The full GPU module set active on `main` at landing time of feature 016. The `module_set_id` value emitted on a no-flag GPU run; unchanged from feature 016's GPU defaults. |
| `reduced-v1` | `ppstructurev3@gpu` only | The legacy GPU set with `use_table_recognition=False` added — see R-017.3 for the audit-driven justification. |
| `cpu-default` | `ppstructurev3@cpu` (CPU singleton) | The CPU lane's existing hard-coded module-disable kwargs (`use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `use_textline_orientation=False`, `use_formula_recognition=False`, `use_seal_recognition=False`, `use_chart_recognition=False`). Identity preset — preset resolution does not mutate the CPU constructor (R-017.6). |
| `stub-default` | stub adapter | Stub-adapter identity preset; no Paddle import; emits an empty `ppstructure_modules_invoked` list on the run_summary (since the stub does not call `engine.predict`). |

Resolving any other string raises `UnknownPresetError` (cause class `UnknownModuleSet`) → exit code 16 (R-017.12).

Adding a future preset (e.g., `reduced-v2` if the FR-001 audit confirms further sub-modules are safe to disable) is a code change to `preprocessing/presets.py` plus a new entry in this table — not a runtime toggle (per /speckit.clarify Q4).

**Rationale**:
- Four values cover the cross-product of two preset-aware profiles (GPU, CPU) × {legacy/default, reduced/landing}: `legacy` and `reduced-v1` for GPU; `cpu-default` and `stub-default` for the two CPU-side identity presets. Two named GPU presets is the minimum that proves the surface and is benchmark-comparable; the spec mandates exactly two at landing per /speckit.clarify Q4.
- Distinct strings for CPU vs stub make absence-as-regression-signal (FR-010) actually informative: a stub-adapter-only test that suddenly emits `module_set_id = "cpu-default"` is a real regression (the stub adapter's plumbing leaked into the live path).

**Alternatives considered**:
- **Three values** (`legacy`, `reduced-v1`, `default`). Rejected: a single `default` for both CPU and stub erases the CPU-vs-stub distinction that's actually useful for diagnosing test infrastructure problems.
- **Five values** (split `legacy` into separate `legacy-cpu` and `legacy-gpu`). Rejected: `legacy` is meaningful only on GPU (the CPU lane's defaults are already the documented disabled set; calling it "legacy-cpu" is misleading because it is what the CPU lane has done since feature 003). The asymmetric naming reflects asymmetric reality.
- **Use the same identifier name across CPU and GPU** (`default`). Rejected for the same reason as the previous alternative — the GPU "legacy" and the CPU defaults differ on `use_table_recognition` (GPU has it on; CPU's table_recognition is irrelevant under `lang="en"` text invoices but nominally on too). Conflating them under one identifier hides that.

## R-017.3: `reduced-v1` membership

**Decision**: The `reduced-v1` preset disables exactly **`use_table_recognition`** beyond the legacy GPU defaults — i.e., the `reduced-v1` constructor call is:

```python
PPStructureV3(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    use_formula_recognition=False,
    use_seal_recognition=False,
    use_chart_recognition=False,
    use_table_recognition=False,         # ← added by reduced-v1
    cpu_threads=1,
    enable_mkldnn=False,
    device="gpu:0",
    lang="en",
)
```

The remaining live-path sub-modules under `reduced-v1` are layout detection (`layout_detection`), text detection (`ocr_det`), and text recognition (`ocr_rec`).

The FR-001 live-path audit at landing time MUST confirm that on a stage 1 vendor-identity invoice, the `legacy` configuration's `ppstructure_modules_invoked` list is exactly `["layout_detection", "table_recognition", "ocr_det", "ocr_rec"]` and the `reduced-v1` configuration's list is exactly `["layout_detection", "ocr_det", "ocr_rec"]` — the audit narrative lands in Appendix B at landing. If the audit shows additional sub-modules that legacy invokes but vendor identity doesn't need, R-017.3 is amended (and `reduced-v1` is updated) before merge.

**Rationale**:
- The legacy GPU constructor call (preflight.py:447 and ocr.py:259) already disables `use_doc_orientation_classify`, `use_doc_unwarping`, `use_textline_orientation`, `use_formula_recognition`, `use_seal_recognition`, `use_chart_recognition`. The only commonly-on PPStructureV3 sub-module not yet disabled in legacy is **table recognition**.
- Table recognition is irrelevant for vendor identity (the vendor name, address, phone, email, tax ID etc. are extracted from text blocks, not from HTML-formatted invoice line-item tables). Disabling it should be safe per FR-004; the audit confirms it.
- The `lang="en"` setting on the constructor already constrains the text recognition path; `use_table_recognition=False` removes the additional table structure model load + per-page table inference cost.
- One disable per landing keeps the audit-confirmation surface small and the change easy to reason about. If two disables were lumped together and the audit later contradicts one of them, the rollback is harder.

**Alternatives considered**:
- **Disable nothing in `reduced-v1`** (i.e., `reduced-v1 == legacy`). Rejected: defeats the purpose of the feature; SC-001 would not be satisfiable.
- **Disable both `use_table_recognition` AND something else** (e.g., a layout sub-module). Rejected without audit evidence: PaddleOCR's PPStructureV3 layout detector is the upstream of OCR det/rec; disabling it would short-circuit `ocr_det` / `ocr_rec` on layout-organized regions and risk regressing FR-003. The other `use_*` flags are already off in legacy.
- **Defer the `reduced-v1` membership to the audit** (i.e., do not pin it in research). Rejected: research must propose a concrete starting point so the audit is comparing two known configurations. The amendment hook stays available if the audit refutes the choice.

## R-017.4: Closed `det_rec_variant_id` vocabulary at landing

**Decision**: Three valid values at landing time, with the legacy variant unchanged from feature 016:

| Value | Detection model | Recognition model | Notes |
|---|---|---|---|
| `legacy` | PaddleOCR's PPStructureV3 default detection model on `lang="en"` (PP-OCRv5 server-grade detector — whatever PPStructureV3 selects when `text_detection_model_name` is not set) | PaddleOCR's PPStructureV3 default recognition model on `lang="en"` (PP-OCRv5 server-grade recognizer) | The variant active on `main` at landing time of feature 016. Selecting `legacy` means the `text_detection_model_name` and `text_recognition_model_name` kwargs are NOT set — PaddleOCR picks its own server defaults. |
| `ppocrv5-mobile` | `PP-OCRv5_mobile_det` | `PP-OCRv5_mobile_rec` | PP-OCRv5 mobile-grade detection + recognition pair. Same architecture family as `legacy`, materially smaller weights and faster per-page inference; comparable accuracy on clean printed Latin-script invoices. |
| `ppocrv4-mobile` | `PP-OCRv4_mobile_det` | `PP-OCRv4_mobile_rec` | PP-OCRv4 mobile-grade detection + recognition pair. Earlier architecture; smaller still; included as a second comparison point so the benchmark covers two distinct architectures, not just two sizes within one. |

Resolving any other string raises `UnknownPresetError` (cause class `UnknownDetRecVariant`) → exit code 16 (R-017.12).

CPU and stub identity presets emit `det_rec_variant_id = "cpu-default"` and `det_rec_variant_id = "stub-default"` respectively (matching the closed vocabulary on the module-set side, R-017.2).

**Rationale**:
- Two lighter variants is the FR-005 minimum ("at least two"). Picking three (legacy + two lighter) lands the smallest set that satisfies FR-005 and gives the FR-015 quality-gate evidence two candidates against the same legacy baseline on the same fixed corpus subset.
- Picking from PaddleOCR's officially supported model set (the `PP-OCRv{4,5}_{server,mobile}_{det,rec}` model zoo) honors the spec's explicit "no custom-trained weights" stance (Assumptions). The PP-OCRv5 mobile pair is the most recent and most likely to be the long-term replacement; the PP-OCRv4 mobile pair gives a second architecture so the benchmark is not single-axis. Both are reachable from the same PaddleOCR weight-download host as the legacy default; no new download host or wheel is introduced.
- Mobile detection + mobile recognition is matched together (rather than mixed mobile-det + server-rec) so each variant is a single coherent pair. Mixing creates more configurations to bench without the matched pairs covering more of the actual deployment space.

**Alternatives considered**:
- **Five lighter variants** (PP-OCRv5_mobile, PP-OCRv4_mobile, PP-OCRv3_mobile, PP-OCRv5_server-quantized, PP-OCRv4_server-quantized). Rejected: doubles the benchmark wall-clock time without proportionally more evidence; the FR-005 floor is two. If the landing benchmark identifies a clear winner among PP-OCRv5_mobile / PP-OCRv4_mobile, future variants can be added as `reduced-v2`-style additions without a fresh feature.
- **One lighter variant only**. Rejected: contradicts FR-005 ("at least two").
- **Custom-quantized detection model**. Rejected: contradicts the Assumptions stance on PaddleOCR-officially-supported weights only.
- **Mixed mobile-det + server-rec pair**. Rejected: not a maintained pair upstream; quality cliffs are harder to attribute to det vs rec.

## R-017.5: CPU-default and stub-adapter identifier values

**Decision**: Pinned strings:

- `module_set_id = "cpu-default"` on every CPU run (regardless of whether `--module-set` was set — warn-and-proceed nullifies the flag's effect on identifier).
- `det_rec_variant_id = "cpu-default"` on every CPU run (same logic).
- `module_set_id = "stub-default"` on every stub-adapter run.
- `det_rec_variant_id = "stub-default"` on every stub-adapter run.

These four strings are defined in `preprocessing/identifiers.py` as module-level constants (`CPU_DEFAULT_MODULE_SET`, `CPU_DEFAULT_DET_REC_VARIANT`, `STUB_DEFAULT_MODULE_SET`, `STUB_DEFAULT_DET_REC_VARIANT`). The CPU singleton path in `preprocessing/ocr.py` and the stub-adapter wiring in `pipeline/corpus_run.py` import them and write them onto `RunSummary` at run-summary build time.

**Rationale**:
- Stable hyphenated lowercase strings match the existing convention for run-level identifiers (`ppstructurev3@cpu`, `ppstructurev3@gpu` profile names) and are grep-friendly.
- Using the same string for both fields on a CPU/stub run means a run-summary line like `..., "module_set_id":"cpu-default", "det_rec_variant_id":"cpu-default", ...` reads at a glance as "vanilla CPU" vs the GPU run's `..., "module_set_id":"reduced-v1", "det_rec_variant_id":"ppocrv5-mobile", ...`.
- Distinct CPU-vs-stub strings preserve the regression signal noted in R-017.2.

**Alternatives considered**:
- **Empty string / `null`**. Rejected: contradicts FR-010 ("absence of either field is itself a regression signal"). An empty string is structurally present but semantically absent.
- **Reuse the profile name** (`module_set_id = "ppstructurev3@cpu"`). Rejected: conflates two orthogonal axes (the profile and the module-set preset). Two runs on the same profile but different presets must produce different `module_set_id` values per SC-003.

## R-017.6: Module-disable mechanism (preset → constructor kwargs)

**Decision**: Preset resolution returns a frozen mapping of constructor kwargs that the GPU preflight and (optionally) future GPU runtime engine constructions splat into the `PPStructureV3(...)` call. CPU singleton construction in `preprocessing/ocr.py` retains its existing hard-coded module-disable kwargs unchanged — preset resolution does NOT alter the CPU constructor call (FR-014: CPU/stub paths must not consume GPU-only preset code; the CPU lane's "default" preset is identity).

```python
# preprocessing/presets.py
@dataclass(frozen=True)
class ModuleSetPreset:
    name: str                          # closed vocabulary value (R-017.2)
    use_kwargs: dict[str, bool]        # e.g., {"use_table_recognition": False, ...}
    audit_callable: Callable[[Any], list[str]]  # wraps engine.predict; returns sub-module list

MODULE_SET_PRESETS: dict[str, ModuleSetPreset] = {
    "legacy":      ModuleSetPreset(name="legacy",      use_kwargs={...legacy GPU kwargs...},      audit_callable=_audit_legacy_gpu),
    "reduced-v1":  ModuleSetPreset(name="reduced-v1",  use_kwargs={...legacy + use_table_recognition=False...}, audit_callable=_audit_reduced_v1_gpu),
    "cpu-default": ModuleSetPreset(name="cpu-default", use_kwargs={},                              audit_callable=_audit_identity_no_op),
    "stub-default":ModuleSetPreset(name="stub-default",use_kwargs={},                              audit_callable=_audit_identity_no_op),
}

def resolve_module_set(name: str) -> ModuleSetPreset: ...
def resolve_det_rec_variant(name: str) -> DetRecVariant: ...
```

`use_kwargs={}` for the CPU/stub identity presets means "no kwargs to splat" — the CPU constructor call is reached without preset-driven kwargs and uses its existing literal defaults. The GPU constructor call in `preflight.py` line 447 changes from passing literal kwargs to splatting `**preset.use_kwargs` (with the explicit literal `device="gpu:0"`, `lang="en"`, `cpu_threads=1`, `enable_mkldnn=False` kept outside the splat for clarity).

**Rationale**:
- Frozen dataclass + closed dict registry makes preset resolution a pure lookup; no runtime mutation, no ordering surprises, easy to test (R-017.12).
- Splatting kwargs at one call site (preflight) means the engine construction logic itself doesn't need to know about presets — just about kwargs. This keeps `preprocessing/ocr.py`'s CPU singleton code untouched (preserving FR-014).
- Identity presets (`use_kwargs={}`) for CPU and stub are explicit no-ops rather than special-cased branches. The CPU lane is reached via `_get_engine("cpu")` which never sees the preset; the run-summary builder consults `identifiers.py`'s pinned constants directly (R-017.5).

**Alternatives considered**:
- **Mutate the engine after construction**. Rejected: PaddleOCR's PPStructureV3 does not expose a public API for re-toggling module-set after init; would require monkey-patching internals.
- **Construct two engines and pick at predict-time**. Rejected: violates feature 015 FR-001 (single engine per process).
- **Conditional kwargs in `_get_engine`**. Rejected: spreads preset-aware code through the CPU singleton path and contradicts FR-014.

## R-017.7: Live-path audit instrumentation (FR-001)

**Decision**: Each `ModuleSetPreset` carries an `audit_callable: Callable[[Any], list[str]]` whose signature is `wrap(engine) -> list[str]`. At run time, `pipeline/corpus_run.py` (and `pipeline/runner.py` for single-doc) calls `audit_callable(engine)` once after the engine is adopted, and the callable returns the closed-vocabulary list of sub-modules invoked during a representative `engine.predict(...)` call against the canonical fixture (R-016.2: page 1 of `inv_001_easy/source.pdf`). The list is recorded onto `RunSummary.ppstructure_modules_invoked` for the run.

The audit callable's implementation MUST:

1. NOT construct a second `PPStructureV3` engine (preserves feature 015 FR-001).
2. Call `engine.predict(np_img)` exactly once on the canonical fixture (or, on CPU/stub, return immediately with an empty list).
3. Record which sub-modules executed by inspecting either (a) `engine.predict`'s returned object structure (PaddleOCR's `PPStructureV3` returns a list of dicts whose keys identify the sub-models that produced each result — `layout_det_results`, `ocr_det_results`, `ocr_rec_results`, `table_results`) or (b) wrap the underlying sub-models' `predict` callables with a counter at engine-construction time. Implementation prefers approach (a) because it is non-invasive (no monkey-patching) and matches the closed `AUDIT_SUB_MODULE_VOCABULARY` enumeration in `identifiers.py`.

The audit callable returns a deterministic sorted list of strings drawn from `AUDIT_SUB_MODULE_VOCABULARY = ("layout_detection", "table_recognition", "ocr_det", "ocr_rec")`. CPU/stub presets return `[]` (empty list — an explicit signal that the audit was not run on this lane). Failures inside the audit callable raise `WarmupError` cause class `AuditError` (mirroring feature 016 R-016.6) → exit code 15 — fail-fast, no run_summary emitted.

**Rationale**:
- Approach (a) (inspect `predict()` results) keeps the audit non-invasive and deterministic: the returned dict keys are part of PaddleOCR's documented API surface for PPStructureV3 ≥ 3.5 and have been stable across the patch versions this feature uses. This is the same surface the existing `preprocessing/ocr.py:611+` page-result conversion already reads.
- Co-locating the audit with engine adoption (post-adopt, pre-first-doc) means the audit runs exactly once per process and the list flows into `RunSummary` before the first per-document `measure_total` opens — keeping the audit out of any per-doc phase timing window.
- The closed `AUDIT_SUB_MODULE_VOCABULARY` (4 strings at landing) makes the run_summary list grep-friendly and forms a closed contract: any new sub-module name appearing in `predict` results in a future PaddleOCR release would be silently dropped from the audit list, which is the safer default than emitting unrecognized strings; a visible regression test asserts the vocabulary is exactly the 4 strings.

**Alternatives considered**:
- **Approach (b) only — wrap sub-model predict callables with monkey-patched counters**. Rejected: monkey-patching inside the engine is fragile across PaddleOCR patch releases and risks affecting per-doc inference timing. Approach (a) is non-invasive and uses documented surface.
- **Audit on every per-doc predict call**. Rejected: redundant — the sub-modules invoked are determined by the constructor's `use_*` kwargs, which are constant across the process lifetime per feature 015 FR-001. One audit per process is correct; per-doc audit would just re-check the same answer.
- **Read the audit from `engine.config` or `engine._config`**. Rejected: those are private attributes and have changed shape across PaddleOCR releases. The `predict()` results dict is stable.
- **Defer the audit to a separate post-run script**. Rejected: contradicts FR-001 ("by code or instrumentation on the live `ppstructurev3@gpu` runtime path"). A separate post-run script is offline analysis, not live-path instrumentation.

## R-017.8: Run-summary `SCHEMA_VERSION` codebase-level bump

**Decision**: `src/ledgerlinc_ocr/pipeline/timing.py:86` `SCHEMA_VERSION = "0.1.3"` → `SCHEMA_VERSION = "0.1.4"`. Every run of the new binary emits `schema_version: "0.1.4"` regardless of preset selection (CPU, stub, GPU-legacy, GPU-reduced). The 0.1.4 schema is a strict superset of 0.1.3: it adds three new top-level fields. Existing 0.1.3 fields (`schema_version`, `kind`, `stack_preset`, `resolved_profiles`, `execution_slice`, `on_failure`, `documents_total`, `documents_succeeded`, `documents_failed`, `profile_initialization_seconds`, `per_document`, `preprocess_lane`, plus the per-document `phase_timings.*` keys including feature 016's `warmup`) MUST NOT be renamed, removed, or have their type changed (FR-009 / FR-019).

The three new top-level fields land in `RunSummary.to_dict()`'s emission order between `preprocess_lane` (the last existing top-level field added by feature 014 T027) and the run summary's terminating brace:

```jsonc
{
  "kind": "run_summary",
  "schema_version": "0.1.4",
  // ... existing 0.1.3 fields ...
  "preprocess_lane": "cpu" | "gpu0" | ...,
  "module_set_id": "cpu-default" | "stub-default" | "legacy" | "reduced-v1",
  "det_rec_variant_id": "cpu-default" | "stub-default" | "legacy" | "ppocrv5-mobile" | "ppocrv4-mobile",
  "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec"]   // empty list on CPU/stub
}
```

**Rationale**:
- Patch bump (0.1.3 → 0.1.4), not minor (0.1.3 → 0.2.0), because the change is strictly additive — no rename, removal, or retype. Matches feature 014/015/016's same patch-bump-per-additive-key precedent.
- Emitting on every run (not gated on GPU lane) is required by FR-010 ("absence of either field is itself a regression signal"). A version emitted only on GPU runs would let CPU regressions slip past consumers who key off `schema_version` to determine which fields to expect.
- Stable insertion order (after `preprocess_lane`) keeps the run_summary line deterministic, which makes it easier to grep/diff in shell loops.

**Alternatives considered**:
- **Bump to 0.2.0**. Rejected: the change is additive; semver patch is the established convention here.
- **Skip the schema_version bump and rely on field presence**. Rejected: contradicts feature 014/015/016's pattern, and feature 016 explicitly bumped to 0.1.3 for a single additive optional key. Consistency matters for downstream consumers tracking `schema_version` to feature-gate parsing.
- **Emit the new fields under an `additive` sub-object**. Rejected: scopes-creep that doesn't match the additive-only pattern (existing one-time GPU phases like `paddle_import` live at top level under `phase_timings`, not under a wrapper).

## R-017.9: `UnknownPresetError` shape and routing

**Decision**: A new `UnknownPresetError(message: str, preset_axis: str, preset_value: str, valid_values: tuple[str, ...])` exception lives in `src/ledgerlinc_ocr/preprocessing/errors.py`, mirroring the `EngineInitError` / `WarmupError` shapes used by feature 014 and 016. `preprocessing/presets.py`'s `resolve_module_set(name)` and `resolve_det_rec_variant(name)` raise it with the appropriate `preset_axis` (`module_set` or `det_rec_variant`) and `valid_values` (the corresponding registry keys as a tuple).

Both CLI entry points (`preprocessing/cli.py` and `pipeline/cli.py`) catch `UnknownPresetError` at the same boundary they already catch `EngineInitError` / `WarmupError`: print `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>` to stderr, exit non-zero (exit code **16**, immediately after feature 016's exit code 15), and emit no `run_summary`.

**Rationale**:
- Reusing the established `EngineInitError` / `WarmupError` shape keeps error-handling code consistent across the preprocessing surface.
- Exit code 16 fits naturally after feature 014's 10–14 GPU-preflight exit codes and feature 016's 15. Operators triaging a stderr line `error: unknown module_set: 'reduced-v99' — valid values are: legacy, reduced-v1, cpu-default, stub-default` know exactly what failed and how to fix it.
- Failing at the CLI boundary (before any engine is constructed) keeps the failure cheap — no Paddle import, no GPU bind probe, no preflight. The check is dirt-fast and CPU-safe (R-017.12).
- Surfacing `valid_values` in the error keeps the contract self-documenting: the operator does not need to read this research doc or `--help` to recover.

**Alternatives considered**:
- **Reuse `EngineInitError`**. Rejected: that error class encodes a different cause taxonomy (`paddle_not_installed`, `gpu_not_exposed`, etc.). Conflating "unknown preset name" with "Paddle could not bind to the GPU" makes diagnostics worse.
- **Print warning + fall back to legacy**. Rejected: contradicts the spirit of R-017.1's warn-and-proceed pattern, which is for cross-profile-cross-axis cases (CPU + GPU-only flag), not for typo'd identifier values. Falling back silently would cause an operator who typo'd `reduced-v01` to think they were running `reduced-v1`.
- **Make the registry case-insensitive**. Rejected: identifiers in this codebase are case-sensitive and lowercase by convention (`ppstructurev3@gpu`, etc.); a mixed-case user input is exactly the kind of typo that should fail loudly.

## R-017.10: Quality-gate metric extraction (FR-015 per Clarifications Q1)

**Decision**: The two-metric gate reads exclusively from the existing evaluator's `evaluation_run_summary.json` artifact emitted under the corpus root after a corpus evaluation run. Specifically:

1. **Aggregate vendor-identity field score**: read the existing `aggregate.field_score` (or whatever `docs/stage1-vendor-identity/scoring.md` names as the per-corpus aggregate score in `evaluation_run_summary.json`) — this is the existing evaluator's headline number on the chosen corpus subset.
2. **Per-document pass count**: count of per-doc `evaluation_document.json` files whose evaluator-emitted `pass: true` flag is set, on the same subset. This count is also exposed at the corpus level inside `evaluation_run_summary.json`'s `documents_passed` (or equivalent existing field — confirmed at landing time when running the evaluator against `--corpus-root` filtered by the R-017.11 subset).

Both metrics are read by a small **plan-time** helper script under `specs/017-ppstructurev3-module-reduction/quickstart.md` Appendix A — the **gate is not a runtime check inside the pipeline**; it is a release-gate procedure run at landing and at any future promotion-decision time. The pipeline knows nothing about the gate; only the operator/researcher running the benchmark consults it. Promotion requires both `candidate_aggregate_field_score >= legacy_aggregate_field_score` AND `candidate_documents_passed >= legacy_documents_passed` on the same subset. Either metric falling below legacy rejects promotion (Clarifications Q1 / FR-015 / SC-008).

The benchmark numbers (legacy vs ppocrv5-mobile vs ppocrv4-mobile, on the R-017.11 5-doc subset) are recorded in `quickstart.md` Appendix A at landing time.

**Rationale**:
- The gate must read existing evaluator outputs (FR-015): no new metric, no new artifact. Both metrics already exist in `evaluation_run_summary.json`.
- Treating the gate as an offline release-gate procedure (rather than a runtime check) keeps the pipeline observability-only: `module_set_id` and `det_rec_variant_id` flow through the run, but the question "should this configuration become the new default" is a promotion decision, not a runtime question.
- Two metrics with simple `>=` comparison is the most directly auditable shape: a future reader can re-derive the promotion decision from the recorded numbers.

**Alternatives considered**:
- **Single combined metric** (e.g., aggregate × pass-count product). Rejected: contradicts /speckit.clarify Q1 (two-metric gate; both must be ≥ legacy).
- **Per-field accuracy gate** (every individual vendor-identity field must not regress beyond a small tolerance). Rejected: was Option D in /speckit.clarify Q1 and not chosen.
- **Wire the gate into `routing_decision.json`**. Rejected: routing is per-document; the gate is per-corpus; categorically wrong layer.
- **Record only the aggregate, not the per-doc count**. Rejected: contradicts /speckit.clarify Q1 (BOTH metrics).

## R-017.11: Fixed corpus subset for benchmarking (FR-005, Assumptions)

**Decision**: The fixed 5-document subset for the FR-005 benchmark and the FR-015 quality gate is:

1. `inv_001_easy` (canonical happy-path fixture; already used in feature 016 R-016.2 as the warmup fixture)
2. `inv_002_easy`
3. One mid-difficulty document — pinned at landing time after running the evaluator against the existing 20-doc corpus to identify a representative mid-difficulty document. **Provisional choice: `inv_007_medium`** (pending corpus inspection at landing).
4. Two challenging documents — pinned similarly. **Provisional choices: `inv_015_hard`, `inv_018_hard`**.

The same 5 documents are used for the legacy run, every lighter det/rec variant under FR-005, and both `module_set_id` presets. Locked in `quickstart.md` Appendix A and in `tests/pipeline/test_det_rec_variant_benchmark.py`'s parameterization.

**Rationale**:
- 5 documents covers the corpus's difficulty range (2 easy, 1 medium, 2 hard) without burning hours per benchmark run. Fewer than 5 risks the per-document pass count being too coarse; more than 5 turns the bench into a half-day operation each time it's repeated.
- Fixed subset across configurations (Assumptions) is required for comparable timing + quality numbers. Drifting the subset between runs would invalidate the gate.
- Pinning the medium and hard names provisionally and confirming at landing keeps research honest — the corpus may have shifted document names between feature 016 landing and this feature's landing; the final pinning happens when the bench actually runs.

**Alternatives considered**:
- **All 20 documents**. Rejected: the bench has to run for every det/rec variant × every module set combination; 5 × 6 = 30 runs at landing if even moderately exhaustive. 20 × 6 = 120 runs is a half-day on this workstation.
- **3 documents** (1 easy, 1 medium, 1 hard). Rejected: too few for meaningful per-document pass count diff signals.
- **A randomly sampled subset per run**. Rejected: the gate would be incomparable across runs.

## R-017.12: Failure handling for unknown / typo'd identifier values

**Decision**: Failing fast at the CLI boundary, before any Paddle import. The behavior matrix:

| Case | Behavior |
|---|---|
| Both flags set to known valid values | Run proceeds. Identifier values land on run_summary. |
| One flag unset (default) | Run proceeds with the active profile's default identifier (e.g., `legacy` on GPU, `cpu-default` on CPU). |
| Either flag set to a known value but cross-profile (e.g., `--module-set=legacy` on CPU) | Warn-and-proceed (R-017.1 / FR-013). The actual `module_set_id` emitted on run_summary is the active profile's default (`cpu-default`). |
| Either flag set to an unknown value | Fail fast: `UnknownPresetError` → exit code 16, stderr `error: unknown <preset_axis>: <value!r> — valid values are: <…>` (R-017.9). No Paddle import. No engine construction. No run_summary emitted. |
| Both flags set to incompatible values (no real combination is incompatible at landing) | N/A — at landing the four `module_set_id` values × five `det_rec_variant_id` values = 20 cells, all valid by construction (R-017.2 × R-017.4). If a future preset introduces an incompatibility, that future feature must define the failure mode. |

Implementation: `preprocessing/cli.py` and `pipeline/cli.py` call `resolve_module_set(...)` and `resolve_det_rec_variant(...)` immediately after argv parsing and BEFORE any Paddle / preflight import. `UnknownPresetError` is caught at the same boundary as `WarmupError` (feature 016 exit code 15 ↔ this feature's exit code 16).

**Rationale**:
- Early failure means an operator typo wastes <100 ms, not the multi-second cost of Paddle import + GPU bind probe + engine construction.
- Distinct exit code (16) lets shell scripts distinguish "unknown preset" from "warmup failed" (15) and from "preflight failed" (10–14).
- Emitting valid values in the stderr message means the operator does not need access to spec / research / `--help` to recover from the error.

**Alternatives considered**:
- **Allow runtime to validate**. Rejected: incurs Paddle import cost just to surface a typo.
- **Warn-and-fallback to default**. Rejected for typo cases (R-017.9 alternative section): silent fallback hides the typo.

## R-017.13: Research artifact location for benchmark + audit narratives

**Decision**: The two narratives FR-001 (live-path audit) and FR-005 (lighter-variant benchmark) require land in:

- **FR-001 audit narrative** → `specs/017-ppstructurev3-module-reduction/research.md` Appendix B at landing. Filled in once. Includes: actual `engine.predict` returned-keys for legacy and reduced-v1 on `inv_001_easy/source.pdf`; the resulting `ppstructure_modules_invoked` lists; confirmation that no field in `preprocess_output.json` is lost between configurations; any audit-driven amendment to R-017.3 if observed sub-modules differ from prediction.
- **FR-005 benchmark numbers** → `specs/017-ppstructurev3-module-reduction/quickstart.md` Appendix A at landing. Filled in once. Includes: per-configuration `phase_timings.*` averages on the 5-doc subset; the existing evaluator's `evaluation_run_summary.json` aggregate field score and per-document pass count for each configuration; the quality-gate decision (passes / fails for each candidate); the recommended GPU default at landing time (likely `legacy` if the gate fails on both candidates; otherwise the candidate that passes by the larger margin per the two-metric ordering).
- **No new persisted artifact**, no new docs page under `docs/stage1-vendor-identity/`, no entry in `contracts/stage1_vendor_identity/AMENDMENTS.md` (FR-019 / FR-020).

If the FR-024 deferral is taken (workstation GPU unavailable at landing), both Appendices are populated with `<deferred — pending GPU verification under tasks T-XX>` placeholders that name the deferred task IDs from `tasks.md`. The deferred items MUST NOT be silently elided.

**Rationale**:
- Research and quickstart are the right home for landing-time observations that don't belong in the runtime contract: audit results are spec-supporting evidence; benchmark numbers are spec-supporting evidence + operator reference.
- Keeping both narratives inside this feature's `specs/017-…/` directory localizes them so a future feature consulting them does not have to chase across `docs/`.
- Refusing to silently elide deferred items (per FR-024) is the same anti-skip discipline feature 016 established.

**Alternatives considered**:
- **New docs/stage1-vendor-identity/ppstructurev3-presets.md page**. Rejected: contradicts the `docs/` precedent (which is operator-facing reference, not landing-time evidence) and risks bit-rot when the registry updates in a future feature.
- **Inline both into spec.md**. Rejected: spec.md is already the largest of the four artifacts; appendices belong with research / quickstart.
- **External wiki / issue tracker**. Rejected: contradicts the in-repo, version-controlled, audit-trail convention.

## Appendix A — Variant model registry (cross-reference with R-017.4)

A flat reference table of the five `det_rec_variant_id` values across all profiles, with the constructor kwargs each one feeds into `PPStructureV3(...)` on the GPU lane. CPU/stub identity presets pass `{}`.

| `det_rec_variant_id` | `text_detection_model_name` | `text_recognition_model_name` | Notes |
|---|---|---|---|
| `legacy` | (unset — PaddleOCR picks PP-OCRv5 server default for `lang="en"`) | (unset — PaddleOCR picks PP-OCRv5 server default for `lang="en"`) | Identical to feature 016's GPU defaults. |
| `ppocrv5-mobile` | `PP-OCRv5_mobile_det` | `PP-OCRv5_mobile_rec` | Smaller than legacy; same architecture family. |
| `ppocrv4-mobile` | `PP-OCRv4_mobile_det` | `PP-OCRv4_mobile_rec` | Earlier architecture; smallest of the three. |
| `cpu-default` | (unset) | (unset) | Identity preset — does not modify the CPU constructor (R-017.6). |
| `stub-default` | (unset) | (unset) | Stub adapter — no Paddle import. |

The model names above match PaddleOCR's officially supported model zoo and reach the same weight-download host as `legacy`'s defaults. No new wheel, no new download host, no custom-trained weights.

## Appendix B — FR-001 live-path audit narrative

> **`<filled at landing time after running the audit>`** — current placeholder. At landing, this section MUST list:
>
> 1. Date, machine, ROCm + paddlepaddle-dcu version of the audit run.
> 2. The exact `engine.predict(np_img)` returned-dict keys observed for `inv_001_easy/source.pdf` page 1 under the `legacy` configuration.
> 3. The same observation under the `reduced-v1` configuration.
> 4. The resulting `ppstructure_modules_invoked` list for each configuration (which lands as a value of the `run_summary` additive field of the same name on every future GPU run).
> 5. Confirmation (or refutation) that no field in `preprocess_output.json` is lost between configurations.
> 6. Any audit-driven amendment to R-017.3 (e.g., if the audit shows `legacy` actually invokes additional sub-modules vendor identity does not need, document them and update `reduced-v1`'s membership).
>
> If GPU verification is deferred per FR-024, this Appendix must list the deferred-task ID(s) from `tasks.md` instead of being silently empty.
