# Determinism & Byte-Stability Checklist: Workstation Paddle GPU Preprocessing Validation

**Purpose**: Validate that determinism requirements are complete, clear, and consistent before implementation
**Created**: 2026-05-06
**Feature**: [spec.md](../spec.md)
**Domain**: CPU byte-stability (FR-017, SC-006) vs. GPU non-determinism, `pipeline_version` lane segment, repeat-run guarantees

> Each item below tests the **requirements**, not the implementation. The
> question is whether spec.md / plan.md / research.md describe the
> determinism contract precisely enough that an implementer cannot
> mis-interpret it.

## Requirement Completeness

- [x] CHK001 - Is "byte-identical" defined for SC-006 (e.g., per-byte SHA-256 stability across repeat runs on the same input, in the same environment)? [Resolved, Spec §SC-006] — SC-006 now defines "byte-identical" as per-byte SHA-256 match between two consecutive runs on the same host environment, naming `inv_001_easy` as the in-tree fixed input.
- [x] CHK002 - Is the GPU lane's repeat-run determinism contract documented (must produce identical bytes? similar bytes? unspecified)? [Resolved, Spec §Out Of Scope + §Assumptions] — Out Of Scope now explicitly excludes GPU-lane byte-level repeat-run determinism; Assumptions states GPU output is recorded but not byte-stable.
- [x] CHK003 - Are the conditions under which CPU `pipeline_version` may legitimately change enumerated (engine SHA bump, paddleocr version change, lane segment addition, dpi change)? [Resolved, Research R-014.2 §Legitimate triggers] — R-014.2 enumerates a closed list of five legitimate triggers; anything outside the list is a regression.
- [x] CHK004 - Is the relationship between `weights_hash7 = "0000000"` (placeholder) and determinism guarantees specified for the GPU lane? [Resolved, Research R-014.2 §weights_hash7 placeholder] — R-014.2 states the placeholder is shared across both lanes, treated as stable for determinism purposes within this feature.

## Requirement Clarity

- [x] CHK005 - Is the `pipeline_version` lane-segment grammar specified with sufficient precision to inverse-parse unambiguously (e.g., is the trailing dot the only separator, are `gpu<N>` digits open-ended)? [Resolved, Research R-014.2 §Normative regex / Data-model §LaneSegment] — Normative regex is now in research; data-model documents the parser behavior including pre-feature defaults and unknown-segment tolerance.
- [x] CHK006 - Are determinism observations vs. determinism inputs distinguished (e.g., is `ppstructurev3_init_seconds` explicitly *not* part of the determinism contract)? [Resolved, Contracts §1.Determinism] — Contracts/cli-contract.md classifies `ppstructurev3_init_seconds` as a wallclock observation, not a determinism input.
- [x] CHK007 - Is the boundary between "intentional one-time `pipeline_version` bump" and "regression" defined in normative requirement language (not just rationale)? [Resolved, Research R-014.2 §Legitimate triggers + Spec §SC-006] — R-014.2 declares any change outside the closed trigger list a regression; SC-006 declares the lane-segment addition a one-time intentional bump.

## Requirement Consistency

- [x] CHK008 - Do FR-017 (CPU determinism) and SC-006 (CPU byte-identity) use compatible terminology (e.g., are "byte-stable" and "byte-identical" interchangeable, or do they mean different things)? [PASS, Spec §FR-017 / §SC-006] — Both use "byte-identical"/"byte-stable" interchangeably; SC-006 now formally defines the term as per-byte SHA-256 equality.
- [x] CHK009 - Do the determinism rules for `pipeline_version` align with the additive-only rules for `run_summary` (R-014.6)? [PASS, Research R-014.2 / R-014.6] — Both follow non-breaking, additive evolution patterns; R-014.6 also formalizes "additive" for run_summary.
- [x] CHK010 - Is the lane segment's position (always trailing, after `dpi<N>`) consistent across all references in spec, plan, and research? [PASS, Research R-014.2 + Data-model §LaneSegment + Contracts §2] — All three sources state the lane segment is the trailing dot-separated segment after `dpi<N>`.

## Acceptance Criteria Quality

- [x] CHK011 - Can SC-006 be objectively verified with a defined test procedure (e.g., a documented `sha256sum` comparison or contract test)? [Resolved, Plan §Contract Test Coverage point 3] — Plan now names `tests/pipeline_tests/test_pipeline_version_cpu_byte_stable.py` running CPU twice and asserting `sha256sum` equality as the SC-006 CI gate.
- [x] CHK012 - Are the fixed inputs that SC-006 verifies against named (which document, which environment, which seed)? [Resolved, Spec §SC-006 + Plan §Contract Test Coverage point 3] — SC-006 now names `tests/stage1_vendor_identity/inv_001_easy/source.pdf` as the fixed input; environment is "same host" per the SC-006 wording.

## Scenario Coverage

- [x] CHK013 - Are determinism requirements for the GPU lane defined under multiple-process invocation (warm-corpus run vs. cold one-shot)? [PASS, Spec §Out Of Scope + §Assumptions] — GPU-lane byte-level determinism is explicitly out of scope for both modes; the spec records but does not assert byte-stability for either.
- [x] CHK014 - Are determinism requirements specified for cross-environment runs (same code, different host) or are they explicitly out of scope? [Resolved, Spec §SC-006 + §Out Of Scope] — SC-006 now scopes byte-identity to "same host environment"; Out Of Scope explicitly excludes cross-host/cross-wheel/cross-OS determinism.
- [x] CHK015 - Are the determinism implications of the `weights_hash7 = "0000000"` placeholder addressed for both lanes? [Resolved, Research R-014.2 §weights_hash7 placeholder] — R-014.2 addresses the placeholder for both lanes; replacing it is deferred to a future feature as a one-time intentional bump.

## Edge Case Coverage

- [x] CHK016 - Is the `pipeline_version` parser's behavior defined when reading an artifact written *before* this feature lands (no lane segment)? [Resolved, Data-model §LaneSegment + Research R-014.2 §Backward-compatible parser default + Contracts §1.pipeline_version parsing] — Pre-feature strings parse as `("cpu", None)`; documented in three places.
- [x] CHK017 - Is determinism behavior under `--no-init` (preflight skips PPStructureV3) explicitly defined or out of scope? [PASS, Spec §FR-004 + Contracts §1.Side-effect contract] — Preflight (with or without `--no-init`) writes nothing per FR-004; preflight is not part of the pipeline determinism contract.

## Non-Functional Requirements

- [x] CHK018 - Is the CI gate that enforces SC-006 specified (which test, which command, which exit code)? [Resolved, Plan §Contract Test Coverage point 3] — Plan now specifies `tests/pipeline_tests/test_pipeline_version_cpu_byte_stable.py`; pytest non-zero exit blocks merge.
- [x] CHK019 - Are determinism requirements layered with the FR-018/FR-019 CI defaults so that GPU non-determinism never causes a false CI failure? [PASS, Spec §FR-018 / §FR-019] — FR-018 forbids requiring GPU at CI defaults; FR-019 requires GPU-gated tests to skip when prerequisites are absent. GPU non-determinism is therefore never exercised on default CI.

## Ambiguities & Conflicts

- [x] CHK020 - Does "no committed corpus baseline regenerated unless determinism is proven and accepted" (FR-025) define what "proven" means (test count, sample size, environment count)? [PASS by deferral, Spec §FR-025 + §Assumptions] — Spec deliberately defers "proven" to a follow-up decision; FR-025 records the gate, Assumptions records the deferral. No stage-1 ambiguity to resolve here.

## Notes

- This checklist tests requirement quality, not implementation behavior.
- Items marked `[Resolved]` had a wording-only gap that was patched in spec/plan/research/data-model/contracts during the 2026-05-06 checklist-resolution pass.
- Items marked `[PASS]` were already satisfied by existing artifacts at the time of evaluation.
- Items marked `[PASS by deferral]` are deliberately left to a follow-up feature per the spec; the spec's deferral is itself the satisfying answer.
