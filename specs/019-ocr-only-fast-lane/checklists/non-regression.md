# Non-Regression Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements protecting features 014 / 015 / 016 / 017 / 018 invariants, default `ppstructurev3@cpu` profile behavior, stub-adapter coverage, CI-without-GPU passability, `@pytest.mark.gpu` test-marker discipline, and the SCHEMA_VERSION lineage are complete, clear, and consistent. This is a release-gate checklist focused on what THIS feature must NOT change.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## Feature 014 / 015 / 016 / 017 / 018 Invariant Preservation (FR-022)

- [x] CHK001 - Are the feature 014 / 015 / 016 / 017 / 018 guarantees this feature must preserve enumerated by FR-number, not just by paraphrase? [Completeness, Spec §FR-022, SC-010]
- [x] CHK002 - Is "PPStructureV3 constructed exactly once per process *when invoked*" (feature 015 FR-001) reasserted with the explicit exception that the engine MAY remain unconstructed under `preprocess_strategy_id = ocr-only-v1` (the "exactly once" guarantee applies *to* PPStructureV3 *when* it is invoked, not as a requirement to invoke it)? [Clarity, Spec §FR-022]
- [x] CHK003 - Is "GPU readiness probed at most once per process" (feature 015 FR-004) reasserted as still binding when the new preprocessing-strategy switch is set? [Consistency, Spec §FR-022]
- [x] CHK004 - Is "single-device-per-process guard" (feature 015 FR-006) reasserted as still binding? [Consistency, Spec §FR-022]
- [x] CHK005 - Is "no silent CPU fallback after `ppstructurev3@gpu` is selected" (feature 015 FR-008) reasserted as still binding (especially since this feature INTRODUCES a different "fallback" — OCR-only → `ppstructurev3` on the same GPU lane — which must not be confused with CPU fallback)? [Clarity, Spec §FR-022, Edge Cases]
- [x] CHK006 - Is the feature 016 `--gpu-warmup` flag's behavior (warn-and-proceed pattern, MIOpen/COMGR cache, `phase_timings.warmup`, `WARMUP_FAILED = 15` exit code) reasserted as untouched? [Consistency, Spec §FR-022]
- [x] CHK007 - Is feature 017's `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` semantics explicitly reasserted as untouched (no rename, no removal, no retyping)? [Consistency, Spec §FR-009, FR-022]
- [x] CHK008 - Is feature 017's `--module-set` and `--det-rec-variant` CLI flag behavior explicitly reasserted as untouched (this feature adds one MORE flag rather than modifying those)? [Consistency, Spec §FR-022]
- [x] CHK009 - Is feature 018's `raster_profile_id` / `region_strategy_id` / `region_strategy_fallback_count` semantics explicitly reasserted as untouched (no rename, no removal, no retyping)? [Consistency, Spec §FR-009, FR-022, FR-026]
- [x] CHK010 - Is feature 018's `--raster-profile` and `--region-strategy` CLI flag behavior explicitly reasserted as untouched? [Consistency, Spec §FR-022, FR-026]
- [x] CHK011 - Is `pipeline_version`'s `.gpu0` / `.cpu0` suffix pattern explicitly preserved across all `preprocess_strategy_id` selections introduced by this feature? [Clarity, Spec §FR-022, SC-010]

## Default ppstructurev3@cpu Profile Behavior

- [x] CHK012 - Is `ppstructurev3@cpu` explicitly named as the default preprocessing profile? [Completeness, Spec §FR-011]
- [x] CHK013 - Is the requirement that no CPU code path imports GPU-only OCR-only-strategy code explicit (so a host without Paddle GPU can run the default suite cleanly)? [Completeness, Spec §FR-014]
- [x] CHK014 - Is the requirement that CPU `preprocess_output.json` outputs are byte-identical to outputs on `main` before this feature lands explicit? [Measurability, Spec §US4 acceptance scenario 2, SC-007]
- [x] CHK015 - Is the warn-and-proceed contract on CPU (per FR-013) parameterized to cover the new preprocessing-strategy flag in all permutations (set / unset; combined with feature 017 / 018 flags)? [Coverage, Spec §FR-013]
- [x] CHK016 - Is the rule that warn-and-proceed produces the SAME exit status as the no-flag CPU run explicit? [Measurability, Spec §FR-013, SC-005]
- [x] CHK017 - Is the rule "the warn-and-proceed CPU path runs no preprocessing-strategy change" explicit (i.e., the CPU path continues to use the existing default strategy regardless of the new flag)? [Clarity, Spec §FR-013, FR-014]

## Stub Adapter Coverage

- [x] CHK018 - Is the stub adapter explicitly subject to the same warn-and-proceed contract as `ppstructurev3@cpu` for the new preprocessing-strategy flag? [Consistency, Spec §FR-013, FR-014]
- [x] CHK019 - Are CPU-default and stub-adapter values for the two new `run_summary` identifier fields explicitly distinguished, or deferred to plan? [Gap, Spec §FR-010, Assumptions]
- [x] CHK020 - Is the stub adapter's `ocr_only_fallback_count` value explicitly defined as `0` (the stub never runs the OCR-only fallback path)? [Clarity, Spec §FR-007, FR-014]
- [x] CHK021 - Is the stub adapter's `preprocess_output.json` shape (when produced) explicitly required to validate against the existing schema regardless of the new flag? [Completeness, Spec §FR-003, FR-020]

## CI-Without-GPU Passability

- [x] CHK022 - Is the requirement that the default test suite passes on a host without Paddle GPU explicit? [Completeness, Spec §FR-024, SC-006]
- [x] CHK023 - Is the requirement that `@pytest.mark.gpu`-marked tests are deselected (not failed) on a host without GPU explicit? [Clarity, Spec §FR-023, SC-006]
- [x] CHK024 - Is the requirement that ALL tests requiring Paddle GPU / ROCm / live `ppstructurev3@gpu` runtime introspection of OCR-only behavior be marked `@pytest.mark.gpu` explicit? [Coverage, Spec §FR-023]
- [x] CHK025 - Is the warn-and-proceed CPU path explicitly required to be covered on the default (no-GPU) test suite per FR-024? [Coverage, Spec §FR-024, SC-006]
- [x] CHK026 - Is the requirement that CPU-only and stub-adapter test suites must continue to pass without GPU explicit? [Completeness, Spec §FR-024]

## @pytest.mark.gpu Test-Marker Discipline

- [x] CHK027 - Is the marker `@pytest.mark.gpu` named identically across spec / plan / quickstart so reviewers can grep for it consistently? [Consistency, Spec §FR-023]
- [x] CHK028 - Is the relationship between `@pytest.mark.gpu` and feature 016 / 017 / 018's marker convention explicit (this feature reuses the same marker, not a new one)? [Traceability, Spec §FR-023]
- [x] CHK029 - Is the rule "GPU-marked tests MAY be deferred per FR-025; deferral MUST be captured in `tasks.md` and `quickstart.md`" explicit so deferred work cannot be quietly skipped? [Completeness, Spec §FR-025]

## SCHEMA_VERSION Lineage And Additivity

- [x] CHK030 - Is the `RunSummary.SCHEMA_VERSION` patch bump (post-feature-018: 0.1.5 → 0.1.6, exact value to be confirmed at plan) explicitly documented and tied to the two additive top-level fields this feature adds? [Gap, Assumptions]
- [x] CHK031 - Is the lineage table (0.1.0 → 0.1.6 with feature ownership per row) expected to be extended at plan time so future readers can trace each field to the feature that added it? [Traceability, Assumptions]
- [x] CHK032 - Is the prohibition on this feature renaming, removing, or retyping ANY existing `run_summary` field explicit (covers all fields predating this feature)? [Completeness, Spec §FR-009, FR-022]
- [x] CHK033 - Is the rule "patch bump = additive only; minor bump would imply non-additive" explicit so a future field rename can never sneak through under a patch bump? [Clarity, Assumptions]

## UnknownPresetError / Exit Code 16 Contract Carry-Forward

- [x] CHK034 - Is the decision "extend `UnknownPresetError.preset_axis` additively (from 4 values post-018 to 5 values post-019) rather than adding a new exception class" expected at plan time? [Gap]
- [x] CHK035 - Is the decision "reuse exit code 16 for unknown values on the new `preprocess_strategy_id` axis rather than adding a new exit code" expected at plan time? [Gap]
- [x] CHK036 - Is the requirement that the stderr message format (`error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>`) be applied consistently across all five axes explicit at plan time? [Consistency]

## Corpus Baseline Immutability (FR-019)

- [x] CHK037 - Are committed corpus baselines under `tests/stage1_vendor_identity/*/` named as off-limits to this feature's PR? [Completeness, Spec §FR-019, SC-007]
- [x] CHK038 - Is the legitimate channel for baseline regeneration named (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow)? [Clarity, Spec §FR-019]
- [x] CHK039 - Is the verification mechanism for SC-007 (PR diff against `main` on baseline paths) executable as written? [Measurability, Spec §SC-007]

## Downstream Stage Compatibility

- [x] CHK040 - Is the requirement that the four downstream consumers (evidence-packet 004, extract 005, router 008, assembler 009, evaluator 007) accept new OCR-only outputs unmodified explicit? [Completeness, Spec §FR-022, US5]
- [x] CHK041 - Is the requirement that fallen-back `ppstructurev3` outputs flow through evidence-packet → extract → route → assemble → evaluate without contract changes explicit? [Coverage, Spec §SC-008]
- [x] CHK042 - Is the requirement that `final_structured_payload.json`'s `trace` block continues to reference `preprocess_output.json` correctly under the new flag explicit? [Consistency, Spec §FR-020, FR-022]

## CPU/Stub Behavior Unchanged Under New Flag

- [x] CHK043 - Is the rule "any GPU-only configuration switch this feature introduces, when EXPLICITLY set in the environment on a CPU profile, produces a `run_summary` line with the CPU-default identifier values, performs no preprocessing-strategy change, emits a clear stderr warning, and exits with the same status as a no-flag CPU run" reasserted in spec so all five sub-rules are visible together? [Coverage, Spec §SC-005]
- [x] CHK044 - Is the rule "absence of `preprocess_strategy_id` or `ocr_only_fallback_count` on `run_summary` is itself a regression signal" explicit on every run kind including stub-adapter? [Coverage, Spec §FR-010, FR-007]

## Q3 Warmup Carry-Forward (post Clarifications Session 2026-05-11 Q3)

- [x] CHK045 - Is the rule "warmup pass *mechanics* (cache, env-default, fixture loader, clock-anomaly check, exit code 15 on failure) are unchanged from feature 016" explicit and distinct from the *binding target* rule? [Clarity, Spec §FR-022, Clarifications Q3]
- [x] CHK046 - Is the rule "the `--gpu-warmup` pass binds the engine implied by the selected `preprocess_strategy_id` only" explicit, with the consequence that `_OCR_ENGINE` is warmed on `ocr-only-v1` and `_ENGINE` is warmed on `ppstructurev3`? [Completeness, Spec §FR-022, Clarifications Q3, R-019.16]
- [x] CHK047 - Is the rule "warmup credit is not transferred across engines" explicit so a fallback document on an `ocr-only-v1` warmup run pays the PPStructureV3 cold-start cost on its own `phase_timings` budget? [Clarity, Spec §FR-022, Edge Cases, R-019.16]
- [x] CHK048 - Is the rule "`phase_timings.warmup` measures the single warmed engine only" explicit (not the sum across engines, not zero-padded for the unconstructed engine)? [Clarity, Spec §Edge Cases, R-019.16]
- [x] CHK049 - Is the prohibition on warming both engines on `ocr-only-v1` explicit (or implied by I-019.16 "the unconstructed engine MUST remain `None`")? [Coverage, contracts/module-invariants.md I-019.16]
- [x] CHK050 - Is the prohibition on skipping warmup entirely on `ocr-only-v1` explicit (or implied by I-019.16's "Forbidden" list)? [Coverage, contracts/module-invariants.md I-019.16]
- [x] CHK051 - Is the `WARMUP_FAILED = 15` exit code semantics carried forward unchanged for OCR-only-engine warmup failures (same exit code, same WarmupError shape, no new error class)? [Consistency, Spec §FR-022, R-019.16]

## Notes

- Items test the spec's text protecting prior-feature invariants — not the implementation that delivers preservation. A `[x]` item asserts "is the spec clear/complete/consistent here?" not "does the code preserve the invariant?".
- This checklist focuses on what THIS feature must NOT change (carry-forward). Forward-looking concerns about the new OCR-only fallback path live in `fallback-path.md`.
