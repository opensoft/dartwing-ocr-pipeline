# Failure-Handling Checklist: PPStructureV3 Preprocessing Migration

**Purpose**: Release-gate validation that the spec covers failure branches under
the new engine — engine-init failure, per-page silent-empty downgrade,
suspicious-layout anomalies, unknown layout labels, ingestion-source status
transitions, fallback-as-doc-only, and determinism under failure — with enough
clarity and coverage to build against. Every item validates the requirements,
not the implementation.
**Created**: 2026-04-22
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + QA)

## Engine Initialization Failure

- [ ] CHK001 Is the behavior when a required model weight cannot be downloaded, cached, or loaded specified (hard-fail, non-zero exit, no artifact written)? [Completeness, Spec §FR-016 §Clarifications 2026-04-22]
- [ ] CHK002 Does the spec require the initialization error message to name BOTH the missing model artifact AND the upstream hoster URL? [Clarity, Spec §FR-016]
- [ ] CHK003 Is the distinction between environmental failure (FR-016, hard-fail, no artifact) and per-document evidence failure (FR-003, artifact-with-warning) made explicit? [Consistency, Spec §FR-016 §FR-003]
- [ ] CHK004 Is the rule "no `status=failure` stub artifact is written on init failure" stated rather than left implicit? [Clarity, Spec §FR-016]
- [ ] CHK005 Is the interaction between FR-015 (no-network after cache) and FR-016 (download-failure behavior) unambiguous — i.e., is the first-run-only nature of the download-failure path stated? [Consistency, Spec §FR-015 §FR-016]
- [ ] CHK006 Are the user-facing channels for the init-failure error specified (stderr, exit code, both)? [Gap, Clarity, Spec §FR-016]
- [ ] CHK007 Is the failure behavior for init errors unrelated to weight downloads (e.g., paddle PIR/oneDNN bug re-firing despite the workaround) specified, or conflated with the weight-download path? [Gap, Spec §FR-016 §Edge Cases]

## Page-Level Zero-Blocks Silent-Failure Downgrade

- [ ] CHK008 Is the trigger condition for FR-003 (`len(raw_ocr_lines) > 0 AND len(blocks) == 0`) specified with unambiguous boolean precedence? [Clarity, Spec §FR-003]
- [ ] CHK009 Does FR-003 specify BOTH actions — append warning AND set `ingestion_sources.paddleocr_vl.status = "failure"` — rather than leaving either implicit? [Completeness, Spec §FR-003]
- [ ] CHK010 Is the rule "a single affected page downgrades the whole document to `failure`" made explicit (vs. a multi-page threshold)? [Clarity, Spec §FR-003 §Assumptions]
- [ ] CHK011 Is the content of the per-page warning specified (names page number, names OCR-line count)? [Completeness, Spec §FR-003 §US2 AC#1]
- [ ] CHK012 Is the distinction between "one page silent-empty among healthy pages" and "all pages silent-empty" preserved in the warning messaging? [Consistency, Spec §US2 AC#3 §Edge Cases]
- [ ] CHK013 Is the rationale for choosing status `"failure"` over a hypothetical `"degraded"` documented, given the frozen contract enum? [Assumption, Spec §US2 AC#3 §Key Entities]

## Suspicious Single-Block Warning (FR-018)

- [ ] CHK014 Is the trigger condition for FR-018 (`len(raw_ocr_lines) >= 2 AND len(blocks) == 1`) specified with an explicit lower bound on OCR-line count? [Clarity, Spec §FR-018]
- [ ] CHK015 Is the rule "FR-018 warns but does NOT downgrade `ingestion_sources.paddleocr_vl.status`" stated rather than left ambiguous? [Completeness, Spec §FR-018 §Clarifications 2026-04-22]
- [ ] CHK016 Is the boundary between FR-003 (zero blocks) and FR-018 (exactly one block) unambiguous — no overlap, no gap? [Consistency, Spec §FR-003 §FR-018]
- [ ] CHK017 Does the warning string format distinguish FR-018's "suspicious layout" from FR-003's silent-empty wording so artifacts can be grep'd? [Clarity, Spec §FR-018 §FR-003]
- [ ] CHK018 Is the behavior for `raw_ocr_lines < 2 AND blocks == 1` specified (no warning, since the trigger's line threshold is not met)? [Coverage, Spec §FR-018]
- [ ] CHK019 Is the interaction between FR-018 and the inv_001 `>=3 blocks` SC-001 gate specified — e.g., does a single-block page on inv_001 fail SC-001 as well as emit the FR-018 warning? [Consistency, Spec §FR-018 §SC-001]

## Label-Mapping Failure (FR-006)

- [ ] CHK020 Is the fallback behavior for an unmapped layout label (`"text"` + per-page warning) specified? [Completeness, Spec §FR-006]
- [ ] CHK021 Does the spec require the unknown-label warning to name BOTH the affected page AND the unmapped label string? [Clarity, Spec §FR-006 §Edge Cases]
- [ ] CHK022 Is the label-mapping behavior ("fall back to `text`") explicitly stated as consistent with the existing 2.10 behavior? [Consistency, Spec §FR-006]
- [ ] CHK023 Is the interaction between unknown-label warnings and `ingestion_sources.paddleocr_vl.status` specified (do unknown labels downgrade status, or only warn)? [Gap, Spec §FR-006]

## Ingestion-Source Status Transitions

- [ ] CHK024 Is the allowed-value set for `ingestion_sources.paddleocr_vl.status` (`success | failure | not_implemented`) reiterated, consistent with the frozen schema? [Consistency, Spec §Key Entities]
- [ ] CHK025 Are the specific conditions that flip status to `"failure"` enumerated (FR-003 silent-empty, aggregate all-pages-empty)? [Completeness, Spec §FR-003 §US2 AC#2]
- [ ] CHK026 Is the condition under which status remains `"success"` despite warnings specified (FR-006 unknown-label alone, FR-018 suspicious-layout alone)? [Clarity, Spec §FR-018 §FR-006]
- [ ] CHK027 Is the aggregate "all pages empty → status=failure" warning preserved and made explicit against the new per-page FR-003 warning? [Consistency, Spec §US2 AC#2]
- [ ] CHK028 Is the decision rule for `status == "not_implemented"` vs `"failure"` clarified — e.g., is `not_implemented` ever emitted by this engine, or reserved for future ingestion sources? [Ambiguity, Spec §Key Entities]

## Blank-Page Handling

- [ ] CHK029 Is a legitimately-blank page (0 OCR lines AND 0 blocks) defined as a recoverable case that does NOT trigger FR-003? [Clarity, Spec §Edge Cases §US2 AC#2]
- [ ] CHK030 Does the spec state that a single blank page alone does NOT downgrade `ingestion_sources.paddleocr_vl.status`? [Completeness, Spec §US2 AC#2]
- [ ] CHK031 Is the "all pages blank" aggregate case distinguished from "one page blank among readable ones" in the status-downgrade rules? [Consistency, Spec §US2 AC#2 §Edge Cases]

## Engine-Workaround Recording (FR-012)

- [ ] CHK032 Does FR-012 specify what constitutes "recording" a workaround (research.md entry with upstream link)? [Completeness, Spec §FR-012 §SC-007]
- [ ] CHK033 Is the scope of FR-012 unambiguous — e.g., does "any engine-specific workaround" cover `enable_mkldnn=False`, `cpu_threads=1`, and module-disable flags uniformly, or only the PIR/oneDNN flag? [Ambiguity, Spec §FR-012 §FR-005]
- [ ] CHK034 Is the removal criterion for the workaround (upstream fix lands) stated as the condition for discard? [Clarity, Spec §FR-012]

## Fallback-as-Doc-Only (FR-017)

- [ ] CHK035 Does FR-017 state the fallback's trigger criteria precisely enough to avoid future-slice ambiguity ("V3 cannot initialize on-corpus after the oneDNN workaround, OR V3 regresses on >1 corpus document")? [Clarity, Spec §FR-017 §Clarifications 2026-04-22]
- [ ] CHK036 Is the prohibition against implementing the fallback as a config flag or runtime auto-fallback explicit? [Completeness, Spec §FR-017]
- [ ] CHK037 Is the single-engine architectural commitment for this slice stated ("preprocessing remains single-engine (V3)")? [Clarity, Spec §FR-017]
- [ ] CHK038 Is the pivot cost of invoking the fallback in a future slice captured (not just the trigger criteria)? [Gap, Spec §FR-017]

## Warnings Contract Consistency

- [ ] CHK039 Are warnings required to be emitted into the `warnings` array (not logs/stdout) for every failure type this migration introduces? [Consistency, Spec §FR-003 §FR-006 §FR-018]
- [ ] CHK040 Is each new warning category (FR-003, FR-006, FR-018) assigned a distinct, grep-friendly message prefix so SC-002's pattern-match test is well-defined? [Clarity, Gap, Spec §FR-003 §FR-006 §FR-018 §SC-002]
- [ ] CHK041 Is the warning-emission ordering across a multi-page document specified (page-ascending), so determinism (FR-004) is not violated? [Gap, Spec §FR-004 §FR-003]

## Schema-Validity Invariant Under Failure

- [ ] CHK042 Does the spec restate the invariant "artifacts produced under failure (FR-003, FR-006, FR-018) MUST still validate against v1.0.0" for each new failure path? [Completeness, Spec §FR-001 §FR-003 §FR-018]
- [ ] CHK043 Is the sole schema-valid-artifact exemption (FR-016 init failure → no artifact at all) explicit, and is the boundary between it and the other failure paths unambiguous? [Consistency, Spec §FR-001 §FR-016]
- [ ] CHK044 Is the behavior when the engine's built-in OCR pass (FR-007) returns zero lines but the layout pass returns blocks specified — symmetric to the FR-003 case, or different? [Gap, Spec §FR-003 §FR-007]

## Determinism Under Failure

- [ ] CHK045 Is the byte-stability requirement (FR-004) extended to failure-path outputs — i.e., two identical silent-empty runs emit identical warnings in identical order? [Completeness, Spec §FR-004]
- [ ] CHK046 Is the init-failure error message itself required to be stable across runs (same missing model → same message), so CI assertions are reliable? [Gap, Spec §FR-004 §FR-016]

## Baseline Regeneration Under Failure Paths

- [ ] CHK047 Does FR-010's per-document commit-note requirement cover documents that newly land on FR-003 `status=failure` under the V3 swap, or only documents with OCR-text diffs? [Coverage, Spec §FR-010 §FR-003]
- [ ] CHK048 Is the handling of a corpus document that cannot be preprocessed at all (FR-016 init failure mid-regen) specified — halt the whole regeneration, or mark and continue? [Gap, Spec §FR-010 §FR-016]

## Measurable Acceptance

- [ ] CHK049 Is SC-002's "zero silent-empty without defensive warning + status=failure downgrade" framed measurably and tied to a concrete grep/pattern test against the regenerated corpus? [Measurability, Spec §SC-002]
- [ ] CHK050 Is SC-004's corpus-validator pass criterion aligned with FR-001's "validates against v1.0.0" even under the new failure paths (so a status=failure artifact still exits 0 in the validator)? [Consistency, Spec §SC-004 §FR-001]

## Notes

- Check items off as completed: `[x]`
- `[Gap]` items here are frequent bug sources — prefer tightening the spec over relying on "obvious" behavior
- Any divergence between "hard-fail, no artifact" (FR-016) and "artifact-with-warning, status=failure" (FR-003, FR-018, FR-006) must be explicit, not contextual
- `[Ambiguity]` markers flag phrasing that a conscientious reader could interpret two ways; resolve before planning
