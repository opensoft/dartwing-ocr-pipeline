# Non-Regression Checklist: DPI Reduction And Region-First Vendor Identity Preprocess

**Purpose**: Validate that requirements protecting features 014 / 015 / 016 / 017 invariants, default `ppstructurev3@cpu` profile behavior, stub adapter coverage, CI-without-GPU passability, `@pytest.mark.gpu` test-marker discipline, the existing `UnknownPresetError` / exit code 16 contract, and the SCHEMA_VERSION lineage are complete, clear, and consistent. This is a release-gate checklist (post-plan).
**Created**: 2026-05-10
**Feature**: [spec.md](../spec.md)

## Feature 014/015/016/017 Invariant Preservation (FR-022)

- [x] CHK001 - Are the feature 014 / 015 / 016 / 017 guarantees this feature must preserve enumerated by FR-number, not just by paraphrase? [Completeness, Spec §FR-022, SC-010]
- [x] CHK002 - Is "PPStructureV3 constructed exactly once per process" (feature 015 FR-001) reasserted as still binding under the FR-007 fallback path (where the same engine instance is reused for the full-page fallback predict)? [Consistency, Spec §FR-022, R-018.9]
- [x] CHK003 - Is "GPU readiness probed at most once per process" (feature 015 FR-004) reasserted as still binding when either new switch is set? [Consistency, Spec §FR-022]
- [x] CHK004 - Is "single-device-per-process guard" (feature 015 FR-006) reasserted as still binding? [Consistency, Spec §FR-022]
- [x] CHK005 - Is "no silent CPU fallback after `ppstructurev3@gpu` is selected" (feature 015 FR-008) reasserted as still binding (especially since this feature INTRODUCES a different "fallback" — region-first → full-page on the same GPU lane — which must not be confused with CPU fallback)? [Clarity, Spec §FR-022, Edge Cases]
- [x] CHK006 - Is the feature 016 `--gpu-warmup` flag's behavior (warn-and-proceed pattern, MIOpen/COMGR cache, `phase_timings.warmup`, `WARMUP_FAILED = 15` exit code) reasserted as untouched? [Consistency, Spec §FR-022, FR-014]
- [x] CHK007 - Is feature 017's `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` semantics explicitly reasserted as untouched (no rename, no removal, no retyping)? [Consistency, Spec §FR-010, FR-022]
- [x] CHK008 - Is feature 017's `--module-set` and `--det-rec-variant` CLI flag behavior explicitly reasserted as untouched (this feature adds two MORE flags rather than modifying those)? [Consistency, Spec §FR-022]
- [x] CHK009 - Is `pipeline_version`'s `.gpu0` / `.cpu0` suffix pattern explicitly preserved across all preset combinations introduced by this feature? [Clarity, Spec §FR-022, SC-010]

## Default `ppstructurev3@cpu` Profile Behavior

- [x] CHK010 - Is `ppstructurev3@cpu` explicitly named as the default preprocessing profile? [Completeness, Spec §FR-012]
- [x] CHK011 - Is the requirement that no CPU code path imports GPU-only DPI / region-strategy code explicit (so a host without Paddle GPU can run the default suite cleanly)? [Completeness, Spec §FR-015]
- [x] CHK012 - Is the requirement that CPU `preprocess_output.json` outputs are byte-identical to outputs on `main` before this feature lands explicit? [Measurability, Spec §US4 acceptance scenario 2, SC-007]
- [x] CHK013 - Is the warn-and-proceed contract on CPU (per FR-014) parameterized to cover BOTH new flags and ALL combinations (`--raster-profile` only, `--region-strategy` only, both set)? [Coverage, Spec §FR-014, contracts/cli-contract.md §3]
- [x] CHK014 - Is the rule that warn-and-proceed produces the SAME exit status as the no-flag CPU run explicit? [Measurability, Spec §FR-014, SC-005]
- [x] CHK015 - Is the rule "the warn-and-proceed CPU path runs no DPI change and no region targeting" explicit (i.e., the CPU rasterizer continues to use 300 DPI from `version.py` and process every page edge-to-edge regardless of the flags)? [Clarity, Spec §FR-014, contracts/module-invariants.md I-018.2]

## Stub Adapter Coverage

- [x] CHK016 - Is the stub adapter explicitly subject to the same warn-and-proceed contract as `ppstructurev3@cpu` for both new flags? [Consistency, Spec §FR-014, contracts/cli-contract.md §3]
- [x] CHK017 - Are CPU-default and stub-adapter values for the three new `run_summary` identifier fields explicitly distinguished (`cpu-default` vs. `stub-default`) so absence-as-regression-signal is informative? [Completeness, Spec §FR-011, contracts/run-summary-schema.md §3]
- [x] CHK018 - Is the stub adapter's `region_strategy_fallback_count` value explicitly defined as `0` (the stub never runs the fallback path)? [Clarity, Spec §FR-009, R-018.8]
- [x] CHK019 - Is the stub adapter's `preprocess_output.json` shape (when produced) explicitly required to validate against the existing schema regardless of the two new flags? [Completeness, Spec §FR-002, FR-020]

## CI-Without-GPU Passability

- [x] CHK020 - Is the requirement that the default test suite passes on a host without Paddle GPU explicit? [Completeness, Spec §FR-024, SC-006]
- [x] CHK021 - Is the requirement that `@pytest.mark.gpu`-marked tests are deselected (not failed) on a host without GPU explicit? [Clarity, Spec §FR-023, SC-006]
- [x] CHK022 - Is the requirement that ALL tests requiring Paddle GPU / ROCm / live `ppstructurev3@gpu` runtime introspection of DPI / region-strategy behavior be marked `@pytest.mark.gpu` explicit? [Coverage, Spec §FR-023]
- [x] CHK023 - Is the warn-and-proceed CPU path explicitly required to be covered on the default (no-GPU) test suite per FR-024? [Coverage, Spec §FR-024, SC-006]
- [x] CHK024 - Is the requirement that CPU-only and stub-adapter test suites must continue to pass without GPU explicit? [Completeness, Spec §FR-024]

## `@pytest.mark.gpu` Test-Marker Discipline

- [x] CHK025 - Is the marker `@pytest.mark.gpu` named identically across spec / plan / quickstart so reviewers can grep for it consistently? [Consistency, Spec §FR-023, plan.md Project Structure]
- [x] CHK026 - Is the relationship between `@pytest.mark.gpu` and feature 016's marker convention explicit (this feature reuses the same marker, not a new one)? [Traceability, Spec §FR-023]
- [x] CHK027 - Is the rule "GPU-marked tests MAY be deferred per FR-025; deferral MUST be captured in `tasks.md` and `quickstart.md`" explicit so deferred work cannot be quietly skipped? [Completeness, Spec §FR-025, quickstart.md Appendix B]

## SCHEMA_VERSION Lineage And Additivity

- [x] CHK028 - Is the `RunSummary.SCHEMA_VERSION` patch bump (0.1.4 → 0.1.5) explicitly documented and tied to the three additive top-level fields this feature adds? [Completeness, R-018.14, contracts/run-summary-schema.md §1]
- [x] CHK029 - Is the lineage table (0.1.0 → 0.1.5 with feature ownership per row) explicit so future readers can trace each field to the feature that added it? [Traceability, contracts/run-summary-schema.md §1]
- [x] CHK030 - Is the prohibition on this feature renaming, removing, or retyping ANY existing `run_summary` field explicit (covers the 13 fields predating this feature: `kind`, `schema_version`, 8 `phase_timings.*` keys flattened to top-level, `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`)? [Completeness, Spec §FR-010, FR-022, contracts/run-summary-schema.md §4]
- [x] CHK031 - Is the rule "patch bump = additive only; minor bump would imply non-additive" explicit so a future field rename can never sneak through under a patch bump? [Clarity, R-018.14]

## `UnknownPresetError` / Exit Code 16 Contract Carry-Forward

- [x] CHK032 - Is the decision "extend `UnknownPresetError.preset_axis: Literal[…]` additively from 2 to 4 values rather than adding a new exception class" explicit and justified? [Clarity, R-018.12, data-model.md §UnknownPresetError]
- [x] CHK033 - Is the decision "reuse exit code 16 for unknown values on the two new axes rather than adding new exit codes" explicit and justified? [Clarity, R-018.12, contracts/cli-contract.md §4]
- [x] CHK034 - Is the requirement that no existing CLI catch site (in `preprocessing/cli.py` or `pipeline/cli.py`) needs modification explicit (the additive widening of `preset_axis` does not break uniform routing)? [Completeness, R-018.12]
- [x] CHK035 - Is the requirement that the stderr message format (`error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>`) is the same across all four axes explicit? [Consistency, R-018.12, contracts/cli-contract.md §3]

## Corpus Baseline Immutability (FR-019)

- [x] CHK036 - Are committed corpus baselines under `tests/stage1_vendor_identity/*/` named as off-limits to this feature's PR? [Completeness, Spec §FR-019, SC-007]
- [x] CHK037 - Is the legitimate channel for baseline regeneration named (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow)? [Clarity, Spec §FR-019]
- [x] CHK038 - Is the verification mechanism for SC-007 (PR diff against `main` on baseline paths) executable as written? [Measurability, Spec §SC-007]

## Downstream Stage Compatibility

- [x] CHK039 - Is the requirement that the four downstream consumers (evidence-packet 004, extract 005, router 008, assembler 009, evaluator 007) accept new GPU outputs unmodified across all evaluated `(raster_profile_id, region_strategy_id)` cells explicit? [Completeness, Spec §FR-022, US5]
- [x] CHK040 - Is the requirement that empty page records (pages 2..N under `header-first-v1`) flow through evidence-packet → extract → route → assemble → evaluate without contract changes explicit? [Coverage, Spec §SC-008, Clarifications Q2, plan.md Constitution Check Principle II]
- [x] CHK041 - Is the requirement that `final_structured_payload.json`'s `trace` block continues to reference `preprocess_output.json` correctly under both new flags explicit? [Consistency, Spec §FR-020, FR-022]

## CPU/Stub Behavior Unchanged Under New Flags

- [x] CHK042 - Is the rule "any GPU-only configuration switch this feature introduces, when EXPLICITLY set in the environment on a CPU profile, produces a `run_summary` line with the CPU-default identifier values, performs no DPI change and no region targeting, emits a clear stderr warning, and exits with the same status as a no-flag CPU run" reasserted in spec / contracts so all five sub-rules are visible together? [Coverage, Spec §SC-005]
- [x] CHK043 - Is the rule "absence of `raster_profile_id`, `region_strategy_id`, or `region_strategy_fallback_count` on `run_summary` is itself a regression signal" explicit on every run kind including stub-adapter? [Coverage, Spec §FR-011, contracts/run-summary-schema.md §2]

## Cross-Section Consistency (Plan ↔ Spec)

- [x] CHK044 - Are the FR-022 carry-forward enumerations in spec.md FR-022 and plan.md Constitution Check (Principle II / Quality Gate 1–7) consistent? [Consistency, Spec §FR-022, plan.md §Constitution Check]
- [x] CHK045 - Is the spec's claim that this feature introduces "no new pinned dependency" consistent with plan.md's Primary Dependencies section (no new entries beyond features 014–017's set)? [Consistency, Spec §Assumptions §1, plan.md §Technical Context]
- [x] CHK046 - Is the SCHEMA_VERSION bump destination (0.1.5) consistent across plan.md / R-018.14 / contracts/run-summary-schema.md / data-model.md? [Consistency]

## Notes

- Items test the spec's text protecting prior-feature invariants — not the implementation that delivers preservation. A `[ ]` item asks "is the spec clear/complete/consistent here?" not "does the code preserve the invariant?".
- This checklist focuses on what THIS feature must NOT change (carry-forward). Forward-looking concerns about the new fallback path live in `fallback-path.md`.
