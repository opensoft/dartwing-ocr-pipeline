# Non-Regression Checklist: PPStructureV3 Module And Model Reduction

**Purpose**: Validate that requirements protecting features 014 / 015 / 016 invariants, default `ppstructurev3@cpu` profile behavior, stub adapter coverage, CI-without-GPU passability, and `@pytest.mark.gpu` test-marker discipline are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-09
**Feature**: [spec.md](../spec.md)

## Feature 014/015/016 Invariant Preservation

- [x] CHK001 - Are the feature 014/015/016 guarantees this feature must preserve enumerated by FR-number, not just by paraphrase? [Completeness, Spec §FR-021, SC-009]
- [x] CHK002 - Is "PPStructureV3 constructed exactly once per process" (feature 015 FR-001) reasserted as still binding? [Consistency, Spec §FR-021, SC-009]
- [x] CHK003 - Is "GPU readiness probed at most once per process" (feature 015 FR-004) reasserted? [Consistency, Spec §FR-021]
- [x] CHK004 - Is the "single-device-per-process guard" (feature 015 FR-006) reasserted? [Consistency, Spec §FR-021]
- [x] CHK005 - Is "no silent CPU fallback after `ppstructurev3@gpu` is selected" (feature 015 FR-008) reasserted and aligned with FR-007 of this feature? [Consistency, Spec §FR-021, FR-007]
- [x] CHK006 - Is "warmup behavior under `--gpu-warmup` unchanged" (feature 016) reasserted with measurable verification? [Measurability, Spec §FR-021, SC-009]
- [x] CHK007 - Is `pipeline_version`'s `.gpu0` / `.cpu0` suffix invariant explicit and aligned with feature 014/015/016? [Consistency, Spec §FR-021]

## Default CPU Profile Byte-Identity

- [x] CHK008 - Is "CPU `preprocess_output.json` outputs MUST be byte-identical to outputs on `main` before this feature lands" explicit? [Completeness, Spec §US4]
- [x] CHK009 - Is "byte-identical" defined precisely (same bytes? same JSON value? same JSON value modulo whitespace?) so reviewers can apply the test? [Clarity, Spec §US4]
- [x] CHK010 - Is the expectation that CPU `run_summary` differs from pre-feature `main` ONLY by the three additive identifier fields explicit? [Clarity, Spec §US4, FR-010]
- [x] CHK011 - Is the prohibition on a CPU-side default change explicit (CPU defaults stay as they are unless a follow-up amendment promotes one)? [Completeness, Spec §Out of Scope]

## CPU/Stub Code-Path Isolation

- [x] CHK012 - Is the prohibition on CPU and stub paths importing GPU-only code (module-disable code, model-variant code) explicit? [Clarity, Spec §FR-014]
- [x] CHK013 - Is "GPU-only code path" defined precisely enough that reviewers can flag a leaking import? [Clarity, Spec §FR-014]
- [x] CHK014 - Is the import-guarding mechanism (lazy import, profile-conditional, runtime-probe-guarded) specified, or is the deferral to plan explicit? [Gap, Spec §FR-014]
- [x] CHK015 - Is "no GPU-only configuration switch is consulted on a CPU/stub run" reasserted alongside the code-import prohibition? [Consistency, Spec §FR-014, US4]

## CI-Without-GPU Passability

- [x] CHK016 - Is "the default test suite MUST pass on a host without Paddle GPU and without ROCm" explicit and binding? [Completeness, Spec §FR-023, SC-005]
- [x] CHK017 - Is "default CI configuration deselects `@pytest.mark.gpu`" explicit? [Completeness, Spec §FR-022]
- [x] CHK018 - Is the warn-and-proceed path required to be exercised on the default (no-GPU) suite per FR-023? [Coverage, Spec §FR-023]
- [x] CHK019 - Is stub-adapter coverage of the warn-and-proceed path explicit? [Completeness, Spec §FR-023, FR-014]
- [x] CHK020 - Is "default test suite passes on a host without Paddle GPU" measurable (CI green on commit on a known reference no-GPU image)? [Measurability, Spec §FR-023, SC-005]

## @pytest.mark.gpu Discipline

- [x] CHK021 - Are all GPU-required tests required to be marked with `@pytest.mark.gpu`? [Completeness, Spec §FR-022]
- [x] CHK022 - Is the list of test categories that MUST carry `@pytest.mark.gpu` enumerated (FR-001 audit verification, FR-005 benchmark, FR-008 GPU `run_summary` checks, FR-015 promotion gate, FR-007 fail-fast on bind failure)? [Coverage, Spec §FR-022]
- [x] CHK023 - Is the prohibition on a GPU-required test being unmarked (so the default suite would fail on a no-GPU host) explicit? [Clarity, Spec §FR-022]
- [x] CHK024 - Is the prohibition on marking CPU-runnable tests as `@pytest.mark.gpu` (so they're silently skipped) explicit? [Gap]

## Committed Corpus Baselines

- [x] CHK025 - Is committed corpus baseline immutability under `tests/stage1_vendor_identity/` explicit? [Completeness, Spec §FR-018, SC-006]
- [x] CHK026 - Is the verification mechanism for SC-006 (PR diff against `main` on baseline paths) executable as written? [Measurability, Spec §SC-006]
- [x] CHK027 - Is the legitimate channel for legitimate baseline regeneration (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow) named so reviewers can identify off-channel changes? [Clarity, Spec §FR-018]

## Legacy Configuration Selectability Post-Promotion

- [x] CHK028 - Is "legacy configuration MUST remain a selectable option after promotion" explicit? [Completeness, Spec §FR-017]
- [x] CHK029 - Is "operator can still invoke the legacy configuration by explicit selection" measurable on a single CLI-flag / env-var test? [Measurability, Spec §FR-017]
- [x] CHK030 - Is FR-017 consistent with the operator-override edge case (operator overrides the new GPU default back to the legacy default)? [Consistency, Spec §FR-017, Edge Cases]

## Boundary With Reserved Features (018, 019)

- [x] CHK031 - Is "this feature MUST NOT change rasterization DPI" (reserved for feature 018) reasserted? [Completeness, Spec §FR-025]
- [x] CHK032 - Is "this feature MUST NOT introduce region-first or header-first processing" (reserved for feature 018) reasserted? [Completeness, Spec §FR-025]
- [x] CHK033 - Is "this feature MUST NOT introduce an OCR-only fast lane" (reserved for feature 019) reasserted? [Completeness, Spec §FR-026]
- [x] CHK034 - Is "this feature is configuration-only on the runtime side and additive-only on the `run_summary` side" framed as a non-regression invariant binding the entire feature? [Clarity, Spec §Out of Scope]

## Cross-Reference With Existing Feature SCs

- [x] CHK035 - Are SC-001 through SC-010 cross-checked for consistency with feature 014/015/016 success criteria so a subsequent regression is detectable? [Coverage, Spec §SC-009]
- [x] CHK036 - Is the additive-identifier delta on CPU `run_summary` the ONLY allowed difference from pre-feature behavior on CPU runs, and is that explicit in BOTH US4 and FR-010? [Consistency, Spec §US4, FR-010]
