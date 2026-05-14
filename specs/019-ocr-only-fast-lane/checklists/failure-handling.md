# Failure-Handling Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements covering the OCR-only → `ppstructurev3` fallback path, warn-and-proceed discipline on CPU/stub, fail-fast on GPU bind, blank-output rejection, OCR-only quality-gate failure handling, operator override, and deferred-verification discipline are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## OCR-Only → ppstructurev3 Fallback Path (FR-005 / Clarifications Q1, Q2)

- [x] CHK001 - Is the four-part FR-005 fallback contract enumerated (fall back on that document + emit `ppstructurev3` `preprocess_output.json` + increment `ocr_only_fallback_count` on `run_summary` + never blank output)? [Completeness, Spec §FR-005, Clarifications Q1]
- [x] CHK002 - Is the prohibition on fail-fast in this scenario explicit (fail-fast was rejected at clarify-time and MUST NOT re-emerge in the implementation)? [Completeness, Spec §FR-005, Edge Cases]
- [x] CHK003 - Is the trigger condition (combined two-threshold check; token count AND detector-confidence aggregate both ≥ thresholds) explicit and unambiguous? [Clarity, Spec §FR-005, Clarifications Q2]
- [x] CHK004 - Is the granularity of the fallback explicit (per-document, not per-page, not per-corpus)? [Clarity, Spec §FR-005, Edge Cases]
- [x] CHK005 - Is the requirement that the fallback's `preprocess_output.json` validates against the existing schema explicit? [Completeness, Spec §FR-005, US3 acceptance scenario 2]
- [x] CHK006 - Is the relationship between FR-005 fallback and FR-007 `ocr_only_fallback_count` explicit (every triggered fallback increments the counter exactly once for that document)? [Consistency, Spec §FR-005, FR-007]
- [x] CHK007 - Is the contract for the partial OCR-only attempt's outputs in a fallen-back document defined (discard partial output; `ppstructurev3` output replaces it), or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK008 - Is `phase_timings.rasterization` accounting for fallen-back documents (combined OCR-only attempt + `ppstructurev3` rasterization time vs. final-only) defined, or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK009 - Is the relationship to feature 018 FR-007 / FR-009 region-first fallback precedent explicit so reviewers can verify consistency (the OCR-only fallback follows the same shape as the region-first fallback)? [Traceability, Spec §FR-005, FR-022]

## Warn-and-Proceed Discipline (Wrong-Profile Switch)

- [x] CHK010 - Is the warn-and-proceed contract for the preprocessing-strategy switch on `ppstructurev3@cpu` enumerated as four required behaviors (warn + no strategy change + proceed normally + same exit status)? [Completeness, Spec §FR-013, Edge Cases]
- [x] CHK011 - Is the stub adapter explicitly subject to the same warn-and-proceed contract as `ppstructurev3@cpu` for the preprocessing-strategy switch? [Consistency, Spec §FR-013, FR-014]
- [x] CHK012 - Is "clear stderr warning" specified concretely enough to be machine-grep-able (format, message keyword, marker line), or is the deferral to plan explicit? [Gap, Spec §FR-013]
- [x] CHK013 - Is the prohibition on silent-ignore explicit and named alongside the prohibition on rejection (refusing the run with non-zero exit)? [Completeness, Spec §FR-013]
- [x] CHK014 - Is "exits with the same status it would have produced without the switch" measurable across the relevant argv permutations (CPU/GPU/stub × strategy-switch-set/unset)? [Measurability, Spec §FR-013, SC-005]
- [x] CHK015 - Is the relationship between FR-013 and feature 016 FR-010 / feature 017 FR-013 / feature 018 FR-014 (warn-and-proceed precedent) explicit so reviewers can verify consistency? [Traceability, Spec §FR-013]

## Fail-Fast Discipline (GPU Bind / Runtime Failure)

- [x] CHK016 - Is the fail-fast contract when an OCR-only configuration's GPU bind fails explicit (no silent CPU fallback after `ppstructurev3@gpu` is selected)? [Completeness, Spec §Edge Cases, FR-022]
- [x] CHK017 - Is "the exit reason MUST identify the active `preprocess_strategy_id`" measurable (does the spec require the named identifier values, including the `(raster_profile_id, region_strategy_id)` pair, to appear in the exit message)? [Clarity, Spec §Edge Cases]
- [x] CHK018 - Is the relationship to feature 015 FR-008 / feature 017 FR-007 / feature 018 ("no silent CPU fallback after `ppstructurev3@gpu` is selected") explicit? [Consistency, Spec §FR-022, Edge Cases]
- [x] CHK019 - Is the contract for an unknown / typo'd `preprocess_strategy_id` value (e.g., `ocr-only-v99`) defined (fail fast vs. fall back to legacy vs. warn-and-proceed), or is the deferral to plan explicit? [Gap]
- [x] CHK020 - Is the contract for `preprocess_strategy_id` combined with feature 018's `raster_profile_id` / `region_strategy_id` defined for all combinations (which combos are valid, which are forbidden, which are unsupported), or is "all combinations valid" explicit per FR-026? [Coverage, Spec §FR-026]

## Blank-Output Regression (OCR-Only Yields Empty)

- [x] CHK021 - Is "OCR-only preset emits a schema-invalid or blank `preprocess_output.json`" defined as a forbidden state, distinct from the FR-005 fallback path which emits `ppstructurev3` output? [Completeness, Spec §FR-005, Edge Cases]
- [x] CHK022 - Is the contract for what happens if the FR-005 fallback ITSELF produces blank output (i.e., `ppstructurev3` also yields no text on this document) defined, or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK023 - Is the relationship between blank-output rejection (Edge Cases) and quality-gate failure (FR-016) consistent (both keep legacy GPU default; neither flips it)? [Consistency, Spec §Edge Cases, FR-016]

## OCR-Only Candidate Quality-Gate Failure

- [x] CHK024 - Is the contract for an OCR-only candidate failing the FR-016 quality gate explicit (candidate rejected; legacy `ppstructurev3` kept as default until regression resolved)? [Completeness, Spec §Edge Cases, FR-016]
- [x] CHK025 - Is the rule that the OCR-only candidate stays selectable via explicit configuration after a gate failure explicit (not removed from the closed vocabulary)? [Consistency, Spec §FR-018, US6 acceptance scenario 3]
- [x] CHK026 - Is the symmetric contract for a combined `(preprocess_strategy_id, raster_profile_id, region_strategy_id)` candidate failing the gate explicit (no promotion; legacy values preserved on all three axes)? [Coverage, Spec §FR-016, FR-018]

## Operator Override (Legacy Stays Selectable Post-Promotion)

- [x] CHK027 - Is the operator-override contract (override new GPU default back to the legacy `preprocess_strategy_id = ppstructurev3` configuration) explicit? [Completeness, Spec §Edge Cases, FR-018]
- [x] CHK028 - Is the override mechanism the same explicit configuration switches this feature introduces (not separate flags) per FR-018? [Consistency, Spec §FR-018, Edge Cases]
- [x] CHK029 - Is "operator can still invoke the legacy configuration by explicit selection" measurable (a specific CLI-flag / env-var invocation can be tested)? [Measurability, Spec §FR-018]

## GPU-Verification Deferral Discipline (FR-025)

- [x] CHK030 - Is the GPU-verification-deferral contract (FR-025) explicit and bounded? [Completeness, Spec §FR-025]
- [x] CHK031 - Is the deferral set enumerated by FR-number (FR-015 benchmark, FR-016 promotion-gate verification, GPU-marked tests for OCR-only behavior)? [Coverage, Spec §FR-025]
- [x] CHK032 - Is the prohibition on "quietly skipping the deferred verification" explicit (deferral MUST be captured in `tasks.md` and `quickstart.md`)? [Completeness, Spec §FR-025]
- [x] CHK033 - Is the relationship to feature 016 FR-014 / feature 017 FR-024 / feature 018 FR-025 (deferral precedent) explicit? [Traceability, Spec §FR-025]

## Side-Effect Containment

- [x] CHK034 - Is the prohibition on the OCR-only path changing per-document `phase_timings` shape stated identically to feature 015's keys + feature 016's `warmup`? [Consistency, Spec §Edge Cases, FR-022]
- [x] CHK035 - Is the prohibition on the OCR-only path altering existing `run_summary` fields (including features 017 and 018's) explicit (additive only on `run_summary`)? [Consistency, Spec §FR-009, FR-022]
- [x] CHK036 - Are timeout / hang failure modes for benchmark runs on the GPU lane addressed, or explicitly deferred (consistent with feature 018's stance)? [Gap]
- [x] CHK037 - Are PDF parsing failures (corrupt PDF, encrypted PDF, zero-page PDF) addressed for the OCR-only preset, or are they covered by the existing 014/015/016/017/018 contracts? [Gap]

## Coverage Discipline (Conditions Preserving Legacy Default)

- [x] CHK038 - Are the conditions under which the legacy GPU configuration is preserved (FR-016 gate failure, deterministic-sufficiency/fallback regression, downstream-contract conflict, GPU bind failure, no promotion decision at landing) listed exhaustively in one place? [Coverage, Spec §Edge Cases]
- [x] CHK039 - Is the warn-and-proceed path verifiable on the default (no-GPU) test suite per FR-024? [Coverage, Spec §FR-024, SC-006]

## Q3 Warmup-Failure Coverage (post Clarifications Session 2026-05-11 Q3)

- [x] CHK040 - Is the contract for `WarmupError` raised by the OCR-only PaddleOCR engine (not PPStructureV3) explicit (same WarmupError shape, same `cause_class` taxonomy, exit code 15, no run_summary emitted)? [Coverage, Spec §FR-022, Clarifications Q3, R-019.16]
- [x] CHK041 - Is the rule "an OCR-only warmup failure does NOT trigger a fall-through to PPStructureV3 warmup" explicit so the user gets a clear `WarmupError` rather than a partial-warmup state? [Coverage, Spec §FR-022, Clarifications Q3]
- [x] CHK042 - Is the rule "a PPStructureV3 cold-start failure on a *fallback* document (not at warmup) raises whatever `EngineInitError` PPStructureV3 normally raises, exits via the existing internal-error path (exit code 3 or as classified), and does NOT downgrade to OCR-only's already-emitted output" explicit, or is the deferral to plan explicit? [Gap, Spec §FR-005, FR-022]

## Notes

- Items test that the spec's failure-handling text is complete/clear/consistent — not that the code under test handles failures correctly.
- The fallback path (Clarifications Q1, Q2) is the single highest-risk surface this feature introduces; CHK001–CHK009 deserve close review at planning time.
