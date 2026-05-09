# GPU Configuration Checklist: PPStructureV3 Module And Model Reduction

**Purpose**: Validate that requirements covering the module-set preset surface, lighter detection/recognition variant evaluation, the configuration-identifier surface on `run_summary`, the live-path module audit, and the quality-gate evidence requirement are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-09
**Feature**: [spec.md](../spec.md)

## Module-Set Preset Surface (FR-002)

- [x] CHK001 - Are the module-set presets at landing exactly enumerated (`legacy` + `reduced-v1`, no more, no fewer)? [Completeness, Spec §FR-002, Clarifications]
- [x] CHK002 - Is the closed-vocabulary nature of `module_set_id` explicit (only listed presets are valid; runtime sub-module toggling is forbidden)? [Clarity, Spec §FR-002, Clarifications]
- [x] CHK003 - Is the source of `reduced-v1`'s sub-module list named (the FR-001 audit's recommended disable set, not a-priori intuition)? [Traceability, Spec §FR-002, FR-001, Assumptions]
- [x] CHK004 - Is the procedure for adding a future preset (`reduced-v2`) defined as "code change + new `module_set_id` value", not a runtime toggle? [Completeness, Spec §FR-002, Clarifications]
- [x] CHK005 - Is the explicit-configuration mechanism for module-set selection (CLI-flag + env-var-fallback per the feature 016 `--gpu-warmup` precedent) defined here, or is the deferral to `/speckit.plan` explicit? [Gap, Spec §Assumptions]
- [x] CHK006 - Is the GPU-only nature of the module-set switch explicit (no behavior change on `ppstructurev3@cpu` or stub adapter)? [Clarity, Spec §FR-002, FR-013]
- [x] CHK007 - Is the candidate module list in Assumptions ("table, formula, chart, document orientation, seal") flagged as illustrative-only (the FR-001 audit, not the spec, determines the actual disable set)? [Clarity, Spec §Assumptions]

## Detection/Recognition Variant Evaluation (FR-005, FR-006)

- [x] CHK008 - Is "at least two lighter detection/recognition model configurations" precise (is it floor-bound at two, or exactly two)? [Clarity, Spec §FR-005]
- [x] CHK009 - Is the source of "lighter" variants named ("PaddleOCR's officially supported model set"; not custom-trained weights)? [Clarity, Spec §Assumptions]
- [x] CHK010 - Is the prohibition on custom-trained weights explicit? [Completeness, Spec §Assumptions]
- [x] CHK011 - Are the specific lighter variants chosen for landing-time benchmarking named, or is the deferral to `/speckit.plan` explicit? [Gap, Spec §Assumptions]
- [x] CHK012 - Is the legacy det/rec variant's status as a permanently selectable option preserved post-evaluation and post-promotion? [Completeness, Spec §FR-006, FR-017]
- [x] CHK013 - Is "explicit configuration per run" for det/rec selection defined consistently with module-set selection (same activation pattern)? [Consistency, Spec §FR-006, Assumptions]
- [x] CHK014 - Is the same fixed corpus subset for all evaluated configurations required so quality and timing numbers are comparable? [Completeness, Spec §FR-005, Assumptions]
- [x] CHK015 - Is "small" corpus subset quantified, or is the deferral to `/speckit.plan` explicit? [Gap, Spec §Assumptions]
- [x] CHK016 - Are per-document `phase_timings.*` required to be emitted for every benchmark run? [Completeness, Spec §FR-005, US2]
- [x] CHK017 - Is vendor-identity quality measurement via the existing evaluator (no new metric introduced) required for every benchmark run? [Completeness, Spec §FR-005, FR-016]

## Configuration Identifier Surface (FR-008, FR-010, SC-003)

- [x] CHK018 - Is the configuration identifier shape (two top-level `run_summary` string fields `module_set_id` + `det_rec_variant_id`) explicit and consistent across FR-008, FR-010, SC-003, the Clarifications session, and the Key Entities entry? [Consistency, Spec §FR-008, FR-010, SC-003, Clarifications]
- [x] CHK019 - Is the human-readable-string requirement (no opaque numeric hashes) explicit for both fields? [Clarity, Spec §FR-008]
- [x] CHK020 - Is the per-axis change semantic explicit: `module_set_id` differs only when module set differs; `det_rec_variant_id` differs only when det/rec differs? [Clarity, Spec §SC-003]
- [x] CHK021 - Is the requirement that BOTH fields are emitted on every run (including default `ppstructurev3@cpu` and stub-adapter runs) explicit? [Completeness, Spec §FR-010]
- [x] CHK022 - Is the absence-of-either-field-is-a-regression-signal property explicit? [Clarity, Spec §FR-010]
- [x] CHK023 - Are CPU-default and stub-adapter values (e.g., `cpu-default`) for both fields specified, or is the deferral to `/speckit.plan` explicit? [Gap, Spec §FR-010, Clarifications]
- [x] CHK024 - Is the requirement that two runs with the same configuration on both axes have identical values for both fields explicit? [Clarity, Spec §SC-003]
- [x] CHK025 - Is the boundary explicit that the identifier surface lives on `run_summary` only, NOT inside `preprocess_output.json`? [Consistency, Spec §FR-009, Assumptions]

## Live-Path Module Audit (FR-001)

- [x] CHK026 - Is the live-path requirement (instrumentation on the active runtime path, NOT on preflight) explicit? [Clarity, Spec §FR-001]
- [x] CHK027 - Is the dual-surface landing of the audit explicit: (a) per-run `ppstructure_modules_invoked` on `run_summary`, (b) richer narrative + raw trace in this feature's research artifact? [Completeness, Spec §FR-001, Clarifications]
- [x] CHK028 - Is `ppstructure_modules_invoked` required to be emitted on every run, including CPU and stub? [Clarity, Spec §FR-001]
- [x] CHK029 - Is the empty-list value for `ppstructure_modules_invoked` on the stub adapter explicit? [Clarity, Spec §FR-001, Clarifications]
- [x] CHK030 - Is "live runtime path" defined operationally (instrumentation hook? per-sub-module execution counter? PaddleX/PPStructure trace API?), or is the deferral to plan explicit? [Gap, Spec §FR-001]
- [x] CHK031 - Is the location of the research-artifact audit specific (`specs/017-ppstructurev3-module-reduction/research.md` or a sibling artifact)? [Clarity, Spec §FR-001, Clarifications]

## Quality-Gate Evidence (FR-015, FR-016, SC-008)

- [x] CHK032 - Is the quality-gate metric set explicitly two metrics: (a) per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json` AND (b) per-document pass count on the same subset? [Completeness, Spec §FR-015, Clarifications, SC-008]
- [x] CHK033 - Is "parity" defined precisely as `candidate_metric >= legacy_metric` for BOTH metrics simultaneously? [Clarity, Spec §FR-015, Clarifications]
- [x] CHK034 - Is the same-corpus-subset requirement explicit for both metrics (same `inv_*` set used to measure legacy and candidate)? [Completeness, Spec §FR-015]
- [x] CHK035 - Is the existing-evaluator-outputs-only constraint explicit (no new metric introduced by this feature)? [Clarity, Spec §FR-015]
- [x] CHK036 - Is gate-evidence recording in this feature's research artifact required and located? [Completeness, Spec §FR-016]
- [x] CHK037 - Is the gate-fails-promotion-rejected outcome explicit (legacy default remains, candidate stays opt-in only)? [Clarity, Spec §FR-015, US6]
- [x] CHK038 - Is the source for "per-document pass" pinned (`docs/stage1-vendor-identity/scoring.md`) so reviewers can resolve any ambiguity in counting? [Traceability, Spec §FR-015, Clarifications]
- [x] CHK039 - Is the link between Clarifications session content and FR-015 / SC-008 wording consistent (both refer to the same two metrics in compatible language)? [Consistency, Spec §Clarifications, FR-015, SC-008]

## Cross-Section Consistency

- [x] CHK040 - Is the requirement that legacy stays selectable post-promotion consistent across FR-017 and the Edge Cases operator-override entry? [Consistency, Spec §FR-017, Edge Cases]
- [x] CHK041 - Is the relationship between FR-001 (audit), FR-002 (presets), and `module_set_id` vocabulary self-consistent (audit informs `reduced-v1` membership, not runtime toggling)? [Consistency, Spec §FR-001, FR-002, Clarifications]
- [x] CHK042 - Is the relationship between FR-005 (benchmark ≥2 lighter variants), FR-006 (each is selectable per-run), and FR-016 (gate evidence recorded) coherent so a single benchmark run produces all three deliverables? [Consistency]
