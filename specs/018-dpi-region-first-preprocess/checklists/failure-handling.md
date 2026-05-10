# Failure-Handling Checklist: DPI Reduction And Region-First Vendor Identity Preprocess

**Purpose**: Validate that requirements covering region-first → full-page fallback, fail-fast on GPU bind, warn-and-proceed on wrong-profile switches, blank-output rejection, and deferred-verification discipline are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-10
**Feature**: [spec.md](../spec.md)

## Region-First Fallback Path (FR-007 / Clarifications Q1)

- [x] CHK001 - Is the four-part FR-007 fallback contract enumerated (fall back on that document + emit full-page `preprocess_output.json` + record on `run_summary` + never blank output)? [Completeness, Spec §FR-007, Clarifications Q1]
- [x] CHK002 - Is the prohibition on fail-fast in this scenario explicit (fail-fast was rejected at clarify-time and MUST NOT re-emerge in the implementation)? [Completeness, Spec §FR-007, Clarifications Q1]
- [x] CHK003 - Is the trigger condition (FR-007 / Clarifications Q3) explicit and unambiguous (whitespace-stripped concat of `blocks[].text` in targeted region empty)? [Clarity, Spec §FR-007, Clarifications Q3]
- [x] CHK004 - Is the granularity of the fallback explicit (per-document, not per-page, not per-corpus)? [Clarity, Spec §FR-007, Clarifications Q1]
- [x] CHK005 - Is the requirement that the fallback's `preprocess_output.json` validates against the existing schema explicit? [Completeness, Spec §FR-007, US2 acceptance scenario 3]
- [x] CHK006 - Is the relationship between FR-007 fallback and FR-009 `region_strategy_fallback_count` explicit (every triggered fallback increments the counter)? [Consistency, Spec §FR-007, FR-009]
- [x] CHK007 - Is the contract for the partial region-first attempt's outputs in a fallen-back document defined (discard partial output; full-page output replaces it), or is the deferral to plan explicit? [Gap]
- [x] CHK008 - Is `phase_timings.rasterization` accounting for fallen-back documents (combined region-first attempt + full-page time vs. final-only) defined, or is the deferral to plan explicit? [Gap, Spec §FR-007, Clarifications Q1]

## Warn-and-Proceed Discipline (Wrong-Profile Switch)

- [x] CHK009 - Is the warn-and-proceed contract for the DPI preset switch on `ppstructurev3@cpu` enumerated as four required behaviors (warn + no DPI change + proceed normally + same exit status)? [Completeness, Spec §FR-014, Edge Cases]
- [x] CHK010 - Is the warn-and-proceed contract for the region-strategy switch on `ppstructurev3@cpu` stated identically to the DPI switch's contract? [Consistency, Spec §FR-014, Edge Cases]
- [x] CHK011 - Is the stub adapter explicitly subject to the same warn-and-proceed contract as `ppstructurev3@cpu` for BOTH switches? [Consistency, Spec §FR-014]
- [x] CHK012 - Is "clear stderr warning" specified concretely enough to be machine-grep-able (format, message keyword, marker line), or is the deferral to plan explicit? [Gap, Spec §FR-014]
- [x] CHK013 - Is the prohibition on silent-ignore explicit and named alongside the prohibition on rejection (refusing the run with non-zero exit)? [Completeness, Spec §FR-014]
- [x] CHK014 - Is "exits with the same status it would have produced without the switch" measurable across the eight argv permutations (CPU/GPU/stub × DPI-switch-set/unset × region-switch-set/unset)? [Measurability, Spec §FR-014, SC-005]
- [x] CHK015 - Is the relationship between FR-014 and feature 016 FR-010 / feature 017 FR-013 (warn-and-proceed precedent) explicit so reviewers can verify consistency? [Traceability, Spec §FR-014]

## Fail-Fast Discipline (GPU Bind / Runtime Failure)

- [x] CHK016 - Is the fail-fast contract when a selected configuration's GPU bind fails explicit (no silent CPU fallback after `ppstructurev3@gpu` is selected)? [Completeness, Spec §Edge Cases, FR-022]
- [x] CHK017 - Is "the exit reason MUST identify the configuration that failed" measurable (does the spec require the named identifier values `(raster_profile_id, region_strategy_id)` to appear in the exit message)? [Clarity, Spec §Edge Cases]
- [x] CHK018 - Is the relationship to feature 015 FR-008 ("no silent CPU fallback after `ppstructurev3@gpu` is selected") explicit? [Consistency, Spec §FR-022, Edge Cases]
- [x] CHK019 - Is the contract for an unknown / typo'd `raster_profile_id` value (e.g., `reduced-v99`) defined (fail fast vs. fall back to legacy vs. warn-and-proceed)? [Gap]
- [x] CHK020 - Is the contract for an unknown / typo'd `region_strategy_id` value (e.g., `header-first-v99`) defined? [Gap]
- [x] CHK021 - Is the contract for both switches set simultaneously to incompatible values (if any combinations exist) defined, or is "all combinations valid" explicit? [Gap]

## Blank-Output Regression (Region-First Yields Empty)

- [x] CHK022 - Is "region-first preset emits a schema-invalid or blank `preprocess_output.json`" defined as a forbidden state, distinct from the FR-007 fallback path which emits full-page output? [Completeness, Spec §FR-007, Edge Cases]
- [x] CHK023 - Is the contract for what happens if the FR-007 fallback ITSELF produces blank output (i.e., full-page also yields no text on this document) defined, or is the deferral to plan explicit? [Gap] — *Acknowledged: the orchestrator runs full-page exactly once on fallback (R-018.7); if full-page also yields no text, the document gets a normal sparse `preprocess_output.json` (schema-valid because `blocks: []` and `raw_ocr_lines: []` are permitted by the existing per-page schema). No double fallback. Behavior is inherited from the existing full-page contract from features 014–017. Recommend adding a one-sentence statement to FR-007 in a future spec amendment if reviewers find this implicit behavior ambiguous.*
- [x] CHK024 - Is the relationship between blank-output rejection (Edge Cases) and quality-gate failure (FR-016) consistent (both keep legacy GPU default; neither flips it)? [Consistency, Spec §Edge Cases, FR-016]

## Reduced-DPI Quality-Gate Failure

- [x] CHK025 - Is the contract for a reduced-DPI candidate failing the FR-016 quality gate explicit (candidate rejected; legacy DPI kept as default until regression resolved)? [Completeness, Spec §Edge Cases, FR-016]
- [x] CHK026 - Is the contract for a region-first candidate failing the FR-016 quality gate stated identically (candidate rejected; legacy region strategy kept)? [Consistency, Spec §Edge Cases, FR-016]
- [x] CHK027 - Is the symmetric contract for a combined `(raster_profile_id, region_strategy_id)` candidate failing the gate explicit (no promotion; both legacy values preserved)? [Coverage, Spec §FR-016, FR-018]

## Operator Override (Legacy Stays Selectable Post-Promotion)

- [x] CHK028 - Is the operator-override contract (override new GPU default back to the legacy `(raster_profile_id, region_strategy_id)` configuration) explicit? [Completeness, Spec §Edge Cases, FR-018]
- [x] CHK029 - Is the override mechanism the same explicit configuration switches this feature introduces (not separate flags) per FR-018? [Consistency, Spec §FR-018, Edge Cases]
- [x] CHK030 - Is "operator can still invoke the legacy configuration by explicit selection" measurable (specific CLI-flag / env-var invocations can be tested for both axes)? [Measurability, Spec §FR-018]

## GPU-Verification Deferral Discipline (FR-025)

- [x] CHK031 - Is the GPU-verification-deferral contract (FR-025) explicit and bounded? [Completeness, Spec §FR-025]
- [x] CHK032 - Is the deferral set enumerated by FR-number (FR-005 four-corner benchmark, FR-016 promotion-gate verification, GPU-marked tests for new presets)? [Coverage, Spec §FR-025]
- [x] CHK033 - Is the prohibition on "quietly skipping the deferred verification" explicit (deferral MUST be captured in `tasks.md` and `quickstart.md`)? [Completeness, Spec §FR-025]
- [x] CHK034 - Is the relationship to feature 016 FR-014 / feature 017 FR-024 (deferral precedent) explicit? [Traceability, Spec §FR-025]

## Side-Effect Containment

- [x] CHK035 - Is the prohibition on either preset axis changing per-document `phase_timings` shape stated identically to feature 015's keys + feature 016's `warmup`? [Consistency, Spec §Edge Cases, FR-022]
- [x] CHK036 - Is the prohibition on either preset axis altering existing `run_summary` fields (including feature 017's three) explicit (additive only on `run_summary`)? [Consistency, Spec §FR-010, FR-022]
- [x] CHK037 - Are timeout / hang failure modes for benchmark runs on the GPU lane addressed, or explicitly deferred? [Gap] — *Acknowledged out of scope: benchmark execution timeouts are a tooling/operator concern (e.g., `timeout` wrapper around the CLI invocation), not a runtime contract this feature owns. The feature 014–017 lineage does not address benchmark timeouts either. If a benchmark hangs in practice, operator response is to kill the run; the partial run produces no `run_summary` line and no `preprocess_output.json`, which the harness already handles as "missing artifact" per the existing dataset-layout contract.*
- [x] CHK038 - Are PDF parsing failures (corrupt PDF, encrypted PDF, zero-page PDF) addressed for the new presets, or are they covered by the existing 014/015/016/017 contracts? [Gap]

## Coverage Discipline (Conditions Preserving Legacy Default)

- [x] CHK039 - Are the conditions under which the legacy GPU configuration is preserved (FR-016 gate failure, deterministic-fallback regression, downstream-contract conflict, GPU bind failure, no promotion decision at landing) listed exhaustively in one place? [Coverage, Spec §Edge Cases]
- [x] CHK040 - Is the warn-and-proceed path verifiable on the default (no-GPU) test suite per FR-024? [Coverage, Spec §FR-024, SC-006]

## Notes

- Items test that the spec's failure-handling text is complete/clear/consistent — not that the code under test handles failures correctly.
- The fallback path (Q1) is the single highest-risk surface this feature introduces; CHK001–CHK008 deserve close review at planning time.
