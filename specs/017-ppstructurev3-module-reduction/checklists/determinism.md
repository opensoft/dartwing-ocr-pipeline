# Determinism Checklist: PPStructureV3 Module And Model Reduction

**Purpose**: Validate that requirements covering deterministic preset resolution, audit-list ordering, run_summary field emission order, schema_version emission, exit code stability, closed vocabularies, and cross-run reproducibility are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-09
**Feature**: [spec.md](../spec.md)
**Marker convention**: `[Gap]` = a missing requirement that should be filled. `[Deferred]` = a landing-time observation tracked under FR-024 (GPU-verification deferral) — visible but not failing the gate.

## Preset Registry & Resolution Determinism

- [x] CHK001 - Are `MODULE_SET_PRESETS` and `DET_REC_VARIANTS` specified as immutable, closed-vocabulary registries with no runtime mutation? [Completeness, Plan §I-1, R-017.2, R-017.4]
- [x] CHK002 - Are the exact registry keys at landing enumerated for both axes (4 module-set, 5 det/rec)? [Completeness, R-017.2, R-017.4]
- [x] CHK003 - Is preset resolution (`resolve_module_set`, `resolve_det_rec_variant`) defined as a pure dict lookup with no side effects? [Clarity, R-017.6]
- [x] CHK004 - Is the order of `valid_values` materialized into the `UnknownPresetError` tuple specified deterministically (e.g., insertion-order, lexicographic, or registry-declaration order)? [Clarity, R-017.9, data-model.md "UnknownPresetError"]
- [x] CHK005 - Is the precedence rule "CLI flag wins over env var" stated identically across both axes (`--module-set` vs `DARTWING_MODULE_SET`; `--det-rec-variant` vs `DARTWING_DET_REC_VARIANT`)? [Consistency, R-017.1, contracts/cli-contract.md §1]
- [x] CHK006 - Is the env-var literal-value handling (whitespace stripping? case sensitivity? trailing-newline handling?) for `DARTWING_MODULE_SET` / `DARTWING_DET_REC_VARIANT` specified or explicitly matched to a known precedent (e.g., feature 016's `DARTWING_GPU_WARMUP` parsing)? [Gap, R-017.1]
- [x] CHK007 - Is the case-sensitive matching policy for identifier values explicit (so `Reduced-V1` is rejected with `UnknownPresetError`, not silently coerced)? [Clarity, R-017.9 alternatives]

## Audit-Callable Determinism

- [x] CHK008 - Is the audit callable's return value specified as a deterministic, lexicographically-sorted list of strings? [Clarity, Plan §I-6, R-017.7]
- [x] CHK009 - Is `AUDIT_SUB_MODULE_VOCABULARY` specified with the exhaustive set of allowed sub-module names at landing (`layout_detection`, `table_recognition`, `ocr_det`, `ocr_rec`)? [Completeness, Plan §I-6, data-model.md]
- [x] CHK010 - Is the silent-drop policy for unknown sub-module names (any string not in `AUDIT_SUB_MODULE_VOCABULARY`) specified deterministically (always drop, no warn, no error)? [Clarity, R-017.7]
- [x] CHK011 - Is the audit invocation count (exactly once per process, between engine adoption and per-document loop) specified? [Clarity, Plan §I-5, R-017.7]
- [x] CHK012 - Is the audit input fixture (page 1 of `inv_001_easy/source.pdf`, reused from feature 016 R-016.2) explicitly named so a future reader knows the audit cannot drift? [Consistency, R-017.7]
- [x] CHK013 - Is the empty-list semantic for CPU/stub identity-preset audit callables specified deterministically (always `[]`, not `None`)? [Clarity, R-017.7, Plan §I-6]
- [x] CHK014 - Is the failure-mode of the audit callable (raise `WarmupError` cause class `AuditError` → exit 15) consistent with feature 016's `WarmupError` cause taxonomy? [Consistency, R-017.7, feature 016 R-016.6]

## run_summary Field-Emission Determinism

- [x] CHK015 - Is the emission order of the three new top-level fields fixed (between `preprocess_lane` and the run_summary's terminating brace, in the order `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`)? [Clarity, contracts/run-summary-schema.md §3, R-017.8]
- [x] CHK016 - Is the requirement that ALL three fields are emitted on EVERY run regardless of profile/preset selection unambiguous? [Completeness, Plan §I-8, FR-008, FR-010]
- [x] CHK017 - Is JSON serialization stability for the run_summary line specified (separator pattern, `ensure_ascii`, deterministic dict key order matching `RunSummary.to_dict()`'s explicit order)? [Gap]
- [x] CHK018 - Is the lexicographic sort of `ppstructure_modules_invoked` items specified at the wire-format level (so a downstream `jq` consumer can rely on order)? [Clarity, Plan §I-6]
- [x] CHK019 - Is the requirement that the four "first-doc one-time GPU phases" (`paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup` from feature 016) co-locate with the three new top-level fields when present specified? [Consistency, contracts/run-summary-schema.md §5]

## Schema-Version Stability

- [x] CHK020 - Is `SCHEMA_VERSION = "0.1.4"` specified as emitted on EVERY run of the new binary regardless of preset selection, profile, or opt-in state? [Completeness, Plan §I-9, R-017.8]
- [x] CHK021 - Is the strict-superset relationship between 0.1.3 and 0.1.4 specified (no removed fields, no renamed fields, no retyped fields)? [Clarity, R-017.8, FR-009]
- [x] CHK022 - Is the additive-only patch-bump convention reasserted from features 014 (0.1.0 → 0.1.1), 015 (0.1.1 → 0.1.2), and 016 (0.1.2 → 0.1.3) so this feature's bump (0.1.3 → 0.1.4) is the same pattern, not a new one? [Consistency, R-017.8]
- [x] CHK023 - Is the single source of truth for `SCHEMA_VERSION` (`pipeline/timing.py:86`) named so reviewers know where to assert "no other module declares its own schema version"? [Traceability, R-017.8]

## Exit-Code Stability

- [x] CHK024 - Is `ExitCode.UNKNOWN_PRESET = 16` specified as a stable public contract that operators and CI scripts may key off directly? [Completeness, R-017.9, data-model.md "ExitCode.UNKNOWN_PRESET"]
- [x] CHK025 - Is the exit-code ordering (0, 1, 10–14 feature 014, 15 feature 016, 16 this feature) reasserted in contracts/cli-contract.md §4 so a future feature knows the next code is 17? [Clarity, contracts/cli-contract.md §4]
- [x] CHK026 - Is the precedence rule "fail-fast wins over warn-and-proceed when both apply" (CPU profile + unknown identifier value) deterministic and singly-stated? [Clarity, Plan §I-11, contracts/cli-contract.md §3]
- [x] CHK027 - Is the prohibition on a future feature reusing exit code 16 for a different cause explicit? [Gap]

## Identifier-String Stability

- [x] CHK028 - Are the four CPU/stub identifier string constants (`CPU_DEFAULT_MODULE_SET`, `CPU_DEFAULT_DET_REC_VARIANT`, `STUB_DEFAULT_MODULE_SET`, `STUB_DEFAULT_DET_REC_VARIANT`) specified as stable public strings? [Completeness, R-017.5, data-model.md "CPU/stub identifier constants"]
- [x] CHK029 - Is the requirement that two runs with the same configuration on both axes have identical `module_set_id` and `det_rec_variant_id` values consistent across SC-003, FR-008, and Plan §I-8? [Consistency]
- [x] CHK030 - Is the per-axis change semantic specified deterministically: `module_set_id` differs ⇔ module set differs; `det_rec_variant_id` differs ⇔ det/rec differs (and only that one changes when only one axis changes)? [Clarity, SC-003, R-017.1]

## Closed-Vocabulary Determinism

- [x] CHK031 - Is the prohibition on adding values to the `MODULE_SET_PRESETS` / `DET_REC_VARIANTS` registries at runtime explicit? [Clarity, Plan §I-1, Plan §I-13]
- [x] CHK032 - Is the test-mock-injection policy ("monkeypatch is permissible in tests; production code path must not mutate the registries") specified? [Clarity, Plan §I-13]
- [x] CHK033 - Is the prohibition on case-insensitive registry lookup explicit, so `Reduced-V1` raises `UnknownPresetError` rather than resolving to `reduced-v1`? [Consistency, R-017.9]

## Cross-Run Reproducibility

- [x] CHK034 - Is byte-identity of `preprocess_output.json` required across runs of the same configuration (e.g., two consecutive `--module-set=legacy` runs on the same fixture)? [Completeness, Plan §I-12, FR-018]
- [x] CHK035 - Is the determinism scope (within a process? across processes on the same host? across hosts?) specified, or is the absence of cross-host determinism guarantee explicit? [Gap]
- [x] CHK036 - Is `paddle.seed(0)` determinism inheritance from feature 015 (single seed per process, applied at engine construction) preserved unchanged by this feature's preset-driven engine construction? [Consistency, FR-021, preprocessing/ocr.py "_seed_paddle_once"]
- [x] CHK037 - Is run_summary determinism preserved across stub/CPU re-runs (same input, same output) so test suites can assert byte-equality? [Coverage, Plan §I-12]

## Boundaries With Non-Determinism Sources

- [x] CHK038 - Is the audit fixture's relationship to the warmup fixture (R-017.7 reuses R-016.2's `inv_001_easy` page 1) explicit, so an unintended drift to a different fixture is detectable? [Consistency, R-017.7]
- [x] CHK039 - Is the upstream-determinism dependency (PaddleOCR's "default" detection/recognition model selection on `lang="en"` is implementation-defined by PaddleOCR ≥ 3.5) flagged as an assumption, so a future PaddleOCR upgrade that changes the default cannot silently change `legacy`'s meaning? [Assumption, R-017.4]
- [x] CHK040 - Is the relationship between `legacy` (PaddleOCR picks default) and the model-name kwargs (`text_detection_model_name=None`, `text_recognition_model_name=None`) explicitly specified, so future model-zoo additions cannot quietly make `legacy` mean something different? [Clarity, R-017.4 Appendix A]

## Landing-Time Determinism Observations [Deferred under FR-024]

- [x] CHK041 - Is the actual `engine.predict(np_img)` returned-dict key set observed under `legacy` and `reduced-v1` on `inv_001_easy/source.pdf` recorded in research.md Appendix B (so the audit's deterministic output is verifiable)? [Deferred, R-017.7, research.md Appendix B]
- [x] CHK042 - Are the actual landing-time benchmark numbers for each variant on the fixed 5-doc subset recorded in quickstart.md Appendix A so cross-run reproducibility can be re-derived later? [Deferred, FR-005, quickstart.md Appendix A]
- [x] CHK043 - Are the exact medium-difficulty and hard-difficulty corpus document names (currently provisional `inv_007_medium`, `inv_015_hard`, `inv_018_hard`) pinned at landing in R-017.11? [Deferred, R-017.11]
