# Module Invariants: `preprocessing/presets.py` and Wiring Sites

**Feature**: 017-ppstructurev3-module-reduction
**Decision source**: spec FR-002, FR-004, FR-007, FR-009, FR-010, FR-014, FR-019, FR-021; research.md R-017.2, R-017.4, R-017.5, R-017.6, R-017.7, R-017.9, R-017.12.

These invariants govern the preset registries, the audit callable, and the wiring sites that thread resolved presets from CLI parse to engine construction to run_summary emission. They are stable across the lifetime of feature 017 and are how tests under `tests/unit/preprocessing/test_presets_*.py` and `tests/pipeline_tests/test_*.py` express their assertions.

## I-1. Closed-vocabulary registries

`MODULE_SET_PRESETS` and `DET_REC_VARIANTS` in `preprocessing/presets.py` are dict literals defined at module load. Their keys are exhaustive at landing time (R-017.2 / R-017.4): adding a new preset requires a code change. Tests assert the literal key sets:

- `set(MODULE_SET_PRESETS.keys()) == {"legacy", "reduced-v1", "cpu-default", "stub-default"}`
- `set(DET_REC_VARIANTS.keys()) == {"legacy", "ppocrv5-mobile", "ppocrv4-mobile", "cpu-default", "stub-default"}`

**Asserted by**: `tests/unit/preprocessing/test_presets_unit.py::test_module_set_registry_keys_are_exhaustive`, `::test_det_rec_variant_registry_keys_are_exhaustive`.

## I-2. Identity presets do not mutate the CPU constructor

`MODULE_SET_PRESETS["cpu-default"].use_kwargs == {}` and `MODULE_SET_PRESETS["stub-default"].use_kwargs == {}`. The CPU singleton constructor in `preprocessing/ocr.py:259` is NOT preset-driven — it retains its hard-coded module-disable kwargs unchanged from feature 016. The identity presets exist for the `module_set_id` run_summary field surface only.

**Asserted by**: `tests/unit/preprocessing/test_presets_unit.py::test_cpu_default_preset_use_kwargs_is_empty`, `::test_stub_default_preset_use_kwargs_is_empty`.

## I-3. GPU-only effects (FR-014)

`preprocessing/presets.py` does NOT import `paddleocr`, `paddle`, or any GPU-only module at load time. Preset resolution (`resolve_module_set`, `resolve_det_rec_variant`) is a pure dict lookup. The module is importable on a host without Paddle GPU, satisfying FR-014's CPU/stub isolation requirement.

The audit callable (R-017.7) attached to GPU presets wraps `engine.predict(...)`; it is invoked only on the GPU code path. The CPU/stub identity-preset audit callables return `[]` immediately without inspecting any engine.

**Asserted by**: `tests/unit/preprocessing/test_presets_unit.py::test_presets_module_top_level_imports_dont_load_paddle` (AST-level check that `presets.py` does not name `paddle`/`paddleocr`/`paddlex`/`PIL`/`pypdfium2` in its top-level imports).

## I-4. No second engine ever (preserves feature 015 FR-001)

The audit callable invoked by `pipeline/corpus_run.py` and `pipeline/runner.py` MUST receive the already-adopted `paddleocr.PPStructureV3` instance and MUST NOT call `PPStructureV3(...)` itself. It MUST NOT touch `ocr._ENGINE` or `ocr._ENGINE_DEVICE` (the singleton is the caller's contract).

**Asserted by**: GPU regression `tests/pipeline_tests/test_module_set_audit_gpu.py @gpu` is **deferred per FR-024** (tracked under T016 in `tasks.md`) and not yet present in this PR. The `id(engine_before) == id(engine_after)` and single-construction guarantees are exercised on CPU via `tests/unit/test_preflight_engine_persistence.py::test_ff2_second_ensure_gpu_ready_short_circuits_no_reconstruction`.

## I-5. One audit pass per process (FR-001 + FR-005 / feature 015 FR-001)

The audit callable is invoked exactly once per process — between engine adoption (preflight succeeded) and the per-document loop opening. The result is recorded onto `RunSummary.ppstructure_modules_invoked` and is NOT recomputed for later documents in the corpus. Re-running the audit per document would be redundant (the sub-modules invoked are determined by the constructor's `use_*` kwargs, which are constant across the process lifetime per feature 015 FR-001).

**Asserted by**: GPU regression `tests/pipeline_tests/test_module_set_audit_gpu.py @gpu` is **deferred per FR-024** (tracked under T016 in `tasks.md`) and not yet present in this PR. CPU-safe coverage of the audit-callable wiring lives in `tests/unit/preprocessing/test_presets_audit_callable.py::test_audit_identity_no_op_returns_empty_list`.

## I-6. Audit list determinism (R-017.7)

The audit callable MUST return a deterministic, lexicographically-sorted list of strings. All elements MUST come from `AUDIT_SUB_MODULE_VOCABULARY = ("layout_detection", "table_recognition", "ocr_det", "ocr_rec")`. Any string outside that set MUST be silently dropped by the audit callable.

**Asserted by**: `tests/unit/preprocessing/test_presets_audit_callable.py::test_audit_callable_returns_sorted_subset_of_closed_vocabulary` and `::test_audit_callable_drops_unknown_keys` (CPU-safe via stub engine; the tests inject mock `predict()` results carrying various sub-module keys including unknown ones, asserts unknown keys are dropped and known keys are sorted).

## I-7. Strict ordering of preset application

The wiring sites — `preprocessing/cli.py` (single-doc), `pipeline/cli.py` (warm corpus), `pipeline/runner.py` (single-doc runner), `pipeline/corpus_run.py` (warm corpus runner) — MUST resolve presets in this order:

1. **At argv parse**: call `resolve_module_set(name)` and `resolve_det_rec_variant(name)`. On `UnknownPresetError`, exit with code 16 BEFORE any Paddle import (R-017.12).
2. **After active profile is known**: if the active `--preprocess-profile` is not `ppstructurev3@gpu` AND either flag was set, emit the FR-013 warn-and-proceed stderr line(s); the resolved presets are dropped on this branch (CPU/stub identifiers are written onto `RunSummary` instead, R-017.5).
3. **Before engine construction (GPU lane only)**: thread the resolved presets into `preflight.py`'s `PPStructureV3(...)` call by splatting `**module_set.use_kwargs` and explicitly passing `text_detection_model_name=det_rec_variant.det_model_name` and `text_recognition_model_name=det_rec_variant.rec_model_name` (when non-None).
4. **After engine adoption**: invoke `module_set.audit_callable(engine)` once; record the returned list onto `RunSummary.ppstructure_modules_invoked`.
5. **At run_summary build**: write `module_set_id` and `det_rec_variant_id` from the resolved presets' `name` fields (or from `identifiers.py`'s pinned constants when on CPU/stub).

**Asserted by**: `tests/unit/preprocessing/test_presets_unknown_value.py` (step 1, CPU-safe), `tests/unit/preprocessing/test_presets_cpu_warn_and_proceed.py` (step 2, CPU-safe), `tests/pipeline_tests/test_module_set_audit_gpu.py @gpu` (steps 3–4, **deferred per FR-024**, tracked under T016 in `tasks.md`), `tests/pipeline_tests/test_run_summary_schema_0_1_4.py` (step 5, CPU-safe).

## I-8. Identifier emission on every run (FR-008 / FR-010)

`RunSummary.to_dict()` emits `module_set_id`, `det_rec_variant_id`, and `ppstructure_modules_invoked` as required keys on every run regardless of profile or preset selection. Default values (CPU/stub paths) come from `preprocessing/identifiers.py`'s pinned constants (`CPU_DEFAULT_MODULE_SET = "cpu-default"`, etc.).

**Asserted by**: `tests/pipeline_tests/test_run_summary_schema_0_1_4.py::test_module_set_id_present_on_every_run`, `::test_det_rec_variant_id_present_on_every_run`, `::test_ppstructure_modules_invoked_present_on_every_run` (CPU-safe).

## I-9. Schema version emitted on every run (FR-008 / R-017.8)

`SCHEMA_VERSION = "0.1.4"` is emitted on every run of the new binary regardless of preset selection or warmup state. Consumers built against 0.1.3 read 0.1.4 output without changes (additive-only superset).

**Asserted by**: `tests/pipeline_tests/test_run_summary_schema_0_1_4.py::test_schema_version_is_0_1_4_codebase_level` and `::test_run_summary_emits_0_1_4_in_json_line` (CPU-safe).

## I-10. Fail-fast on unknown preset value (R-017.9 / R-017.12)

`UnknownPresetError` raised in `preprocessing/presets.py` is caught at the same CLI boundary `WarmupError` is caught (feature 016 R-016.6). Stderr line is `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>`. Exit code is 16. No `run_summary` is emitted. No engine is constructed. No `preprocess_output.json` is written.

**Asserted by**: `tests/unit/preprocessing/test_presets_unknown_value.py::test_unknown_module_set_value_returns_exit_16`, `::test_unknown_det_rec_variant_value_returns_exit_16`, `::test_no_run_summary_emitted_on_unknown_preset` (single-doc CLI path), and `::test_pipeline_cli_unknown_module_set_returns_exit_16` (warm-corpus CLI path).

## I-11. Warn-and-proceed precedence (FR-013 vs R-017.12)

When BOTH apply (CPU/stub profile AND unknown identifier value), fail-fast wins — the unknown-value check at step 1 of I-7 runs BEFORE the cross-profile check at step 2. Operators get exit code 16 and the unknown-value stderr line, never the cross-profile warning, on this path.

**Asserted by**: `tests/unit/preprocessing/test_presets_unknown_value.py::test_unknown_value_on_cpu_profile_fails_fast_not_warn`.

## I-12. Legacy byte-identity (FR-018 / SC-006 / Non-regression CHK008)

A `--module-set=legacy --det-rec-variant=legacy` run on `ppstructurev3@gpu` MUST produce a `preprocess_output.json` byte-identical to a `--module-set` / `--det-rec-variant` no-flag run on the same fixture. Same for the CPU lane with `--module-set=cpu-default --det-rec-variant=cpu-default` (a no-op on CPU since identity presets do not mutate the CPU constructor) — byte-identical to the no-flag CPU run on the same fixture.

**Asserted by**: contract-level coverage via `tests/pipeline_tests/test_no_contract_diff.py` (asserts `contracts/stage1_vendor_identity/` is byte-identical to base) and `tests/pipeline_tests/test_legacy_remains_selectable.py::test_explicit_legacy_selection_emits_legacy_identifiers`. The CPU `--module-set=cpu-default` byte-identity test (T030) is **deferred per `tasks.md` deferral table** as test-infrastructure polish; the GPU equivalent (T030 GPU) is **deferred per FR-024**.

## I-13. Preset registries are frozen at module load

`MODULE_SET_PRESETS` and `DET_REC_VARIANTS` are not mutated after `preprocessing/presets.py` is imported. The dict literals are constructed once at module load and never re-bound. Tests that inject test-only presets MUST use `monkeypatch` against the dict object (which is fine for tests) but the production code path MUST NOT modify the registries at runtime.

**Asserted by**: the production registries are typed as `Mapping[str, ModuleSetPreset]` and constructed with `MappingProxyType(...)` (see `preprocessing/presets.py`), which raises `TypeError` on any attempted in-place mutation. CPU-safe coverage via `tests/unit/preprocessing/test_presets_unit.py::test_resolve_module_set_does_not_invoke_audit_callable` (uses `monkeypatch.setattr` on the module-bound name rather than mutating the registry, exercising the test-time substitution pattern this invariant requires).
