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

- [X] CHK001 Is the behavior when a required model weight cannot be downloaded, cached, or loaded specified (hard-fail, non-zero exit, no artifact written)? [Completeness, Spec §FR-016 §Clarifications 2026-04-22]
- [X] CHK002 Does the spec require the initialization error message to name BOTH the missing model artifact AND the upstream hoster URL? [Clarity, Spec §FR-016]
- [X] CHK003 Is the distinction between environmental failure (FR-016, hard-fail, no artifact) and per-document evidence failure (FR-003, artifact-with-warning) made explicit? [Consistency, Spec §FR-016 §FR-003]
- [X] CHK004 Is the rule "no `status=failure` stub artifact is written on init failure" stated rather than left implicit? [Clarity, Spec §FR-016]
- [X] CHK005 Is the interaction between FR-015 (no-network after cache) and FR-016 (download-failure behavior) unambiguous — i.e., is the first-run-only nature of the download-failure path stated? [Consistency, Spec §FR-015 §FR-016]
- [X] CHK006 Are the user-facing channels for the init-failure error specified (stderr, exit code, both)? [Gap, Clarity, Spec §FR-016]
- [X] CHK007 Is the failure behavior for init errors unrelated to weight downloads (e.g., paddle PIR/oneDNN bug re-firing despite the workaround) specified, or conflated with the weight-download path? [Gap, Spec §FR-016 §Edge Cases]

## Page-Level Zero-Blocks Silent-Failure Downgrade

- [X] CHK008 Is the trigger condition for FR-003 (`len(raw_ocr_lines) > 0 AND len(blocks) == 0`) specified with unambiguous boolean precedence? [Clarity, Spec §FR-003]
- [X] CHK009 Does FR-003 specify BOTH actions — append warning AND set `ingestion_sources.paddleocr_vl.status = "failure"` — rather than leaving either implicit? [Completeness, Spec §FR-003]
- [X] CHK010 Is the rule "a single affected page downgrades the whole document to `failure`" made explicit (vs. a multi-page threshold)? [Clarity, Spec §FR-003 §Assumptions]
- [X] CHK011 Is the content of the per-page warning specified (names page number, names OCR-line count)? [Completeness, Spec §FR-003 §US2 AC#1]
- [X] CHK012 Is the distinction between "one page silent-empty among healthy pages" and "all pages silent-empty" preserved in the warning messaging? [Consistency, Spec §US2 AC#3 §Edge Cases]
- [X] CHK013 Is the rationale for choosing status `"failure"` over a hypothetical `"degraded"` documented, given the frozen contract enum? [Assumption, Spec §US2 AC#3 §Key Entities]

## Suspicious Single-Block Warning (FR-018)

- [X] CHK014 Is the trigger condition for FR-018 (`len(raw_ocr_lines) >= 2 AND len(blocks) == 1`) specified with an explicit lower bound on OCR-line count? [Clarity, Spec §FR-018]
- [X] CHK015 Is the rule "FR-018 warns but does NOT downgrade `ingestion_sources.paddleocr_vl.status`" stated rather than left ambiguous? [Completeness, Spec §FR-018 §Clarifications 2026-04-22]
- [X] CHK016 Is the boundary between FR-003 (zero blocks) and FR-018 (exactly one block) unambiguous — no overlap, no gap? [Consistency, Spec §FR-003 §FR-018]
- [X] CHK017 Does the warning string format distinguish FR-018's "suspicious layout" from FR-003's silent-empty wording so artifacts can be grep'd? [Clarity, Spec §FR-018 §FR-003]
- [X] CHK018 Is the behavior for `raw_ocr_lines < 2 AND blocks == 1` specified (no warning, since the trigger's line threshold is not met)? [Coverage, Spec §FR-018]
- [X] CHK019 Is the interaction between FR-018 and the inv_001 `>=3 blocks` SC-001 gate specified — e.g., does a single-block page on inv_001 fail SC-001 as well as emit the FR-018 warning? [Consistency, Spec §FR-018 §SC-001]

## Label-Mapping Failure (FR-006)

- [X] CHK020 Is the fallback behavior for an unmapped layout label (`"text"` + per-page warning) specified? [Completeness, Spec §FR-006]
- [X] CHK021 Does the spec require the unknown-label warning to name BOTH the affected page AND the unmapped label string? [Clarity, Spec §FR-006 §Edge Cases]
- [X] CHK022 Is the label-mapping behavior ("fall back to `text`") explicitly stated as consistent with the existing 2.10 behavior? [Consistency, Spec §FR-006]
- [X] CHK023 Is the interaction between unknown-label warnings and `ingestion_sources.paddleocr_vl.status` specified (do unknown labels downgrade status, or only warn)? [Gap, Spec §FR-006]

## Ingestion-Source Status Transitions

- [X] CHK024 Is the allowed-value set for `ingestion_sources.paddleocr_vl.status` (`success | failure | not_implemented`) reiterated, consistent with the frozen schema? [Consistency, Spec §Key Entities]
- [X] CHK025 Are the specific conditions that flip status to `"failure"` enumerated (FR-003 silent-empty, aggregate all-pages-empty)? [Completeness, Spec §FR-003 §US2 AC#2]
- [X] CHK026 Is the condition under which status remains `"success"` despite warnings specified (FR-006 unknown-label alone, FR-018 suspicious-layout alone)? [Clarity, Spec §FR-018 §FR-006]
- [X] CHK027 Is the aggregate "all pages empty → status=failure" warning preserved and made explicit against the new per-page FR-003 warning? [Consistency, Spec §US2 AC#2]
- [X] CHK028 Is the decision rule for `status == "not_implemented"` vs `"failure"` clarified — e.g., is `not_implemented` ever emitted by this engine, or reserved for future ingestion sources? [Ambiguity, Spec §Key Entities]

## Blank-Page Handling

- [X] CHK029 Is a legitimately-blank page (0 OCR lines AND 0 blocks) defined as a recoverable case that does NOT trigger FR-003? [Clarity, Spec §Edge Cases §US2 AC#2]
- [X] CHK030 Does the spec state that a single blank page alone does NOT downgrade `ingestion_sources.paddleocr_vl.status`? [Completeness, Spec §US2 AC#2]
- [X] CHK031 Is the "all pages blank" aggregate case distinguished from "one page blank among readable ones" in the status-downgrade rules? [Consistency, Spec §US2 AC#2 §Edge Cases]

## Engine-Workaround Recording (FR-012)

- [X] CHK032 Does FR-012 specify what constitutes "recording" a workaround (research.md entry with upstream link)? [Completeness, Spec §FR-012 §SC-007]
- [X] CHK033 Is the scope of FR-012 unambiguous — e.g., does "any engine-specific workaround" cover `enable_mkldnn=False`, `cpu_threads=1`, and module-disable flags uniformly, or only the PIR/oneDNN flag? [Ambiguity, Spec §FR-012 §FR-005]
- [X] CHK034 Is the removal criterion for the workaround (upstream fix lands) stated as the condition for discard? [Clarity, Spec §FR-012]

## Fallback-as-Doc-Only (FR-017)

- [X] CHK035 Does FR-017 state the fallback's trigger criteria precisely enough to avoid future-slice ambiguity ("V3 cannot initialize on-corpus after the oneDNN workaround, OR V3 regresses on >1 corpus document")? [Clarity, Spec §FR-017 §Clarifications 2026-04-22]
- [X] CHK036 Is the prohibition against implementing the fallback as a config flag or runtime auto-fallback explicit? [Completeness, Spec §FR-017]
- [X] CHK037 Is the single-engine architectural commitment for this slice stated ("preprocessing remains single-engine (V3)")? [Clarity, Spec §FR-017]
- [X] CHK038 Is the pivot cost of invoking the fallback in a future slice captured (not just the trigger criteria)? [Gap, Spec §FR-017]

## Warnings Contract Consistency

- [X] CHK039 Are warnings required to be emitted into the `warnings` array (not logs/stdout) for every failure type this migration introduces? [Consistency, Spec §FR-003 §FR-006 §FR-018]
- [X] CHK040 Is each new warning category (FR-003, FR-006, FR-018) assigned a distinct, grep-friendly message prefix so SC-002's pattern-match test is well-defined? [Clarity, Gap, Spec §FR-003 §FR-006 §FR-018 §SC-002]
- [X] CHK041 Is the warning-emission ordering across a multi-page document specified (page-ascending), so determinism (FR-004) is not violated? [Gap, Spec §FR-004 §FR-003]

## Schema-Validity Invariant Under Failure

- [X] CHK042 Does the spec restate the invariant "artifacts produced under failure (FR-003, FR-006, FR-018) MUST still validate against v1.0.0" for each new failure path? [Completeness, Spec §FR-001 §FR-003 §FR-018]
- [X] CHK043 Is the sole schema-valid-artifact exemption (FR-016 init failure → no artifact at all) explicit, and is the boundary between it and the other failure paths unambiguous? [Consistency, Spec §FR-001 §FR-016]
- [X] CHK044 Is the behavior when the engine's built-in OCR pass (FR-007) returns zero lines but the layout pass returns blocks specified — symmetric to the FR-003 case, or different? [Gap, Spec §FR-003 §FR-007]

## Determinism Under Failure

- [X] CHK045 Is the byte-stability requirement (FR-004) extended to failure-path outputs — i.e., two identical silent-empty runs emit identical warnings in identical order? [Completeness, Spec §FR-004]
- [X] CHK046 Is the init-failure error message itself required to be stable across runs (same missing model → same message), so CI assertions are reliable? [Gap, Spec §FR-004 §FR-016]

## Baseline Regeneration Under Failure Paths

- [X] CHK047 Does FR-010's per-document commit-note requirement cover documents that newly land on FR-003 `status=failure` under the V3 swap, or only documents with OCR-text diffs? [Coverage, Spec §FR-010 §FR-003]
- [X] CHK048 Is the handling of a corpus document that cannot be preprocessed at all (FR-016 init failure mid-regen) specified — halt the whole regeneration, or mark and continue? [Gap, Spec §FR-010 §FR-016]

## Measurable Acceptance

- [X] CHK049 Is SC-002's "zero silent-empty without defensive warning + status=failure downgrade" framed measurably and tied to a concrete grep/pattern test against the regenerated corpus? [Measurability, Spec §SC-002]
- [X] CHK050 Is SC-004's corpus-validator pass criterion aligned with FR-001's "validates against v1.0.0" even under the new failure paths (so a status=failure artifact still exits 0 in the validator)? [Consistency, Spec §SC-004 §FR-001]

## Notes

- Check items off as completed: `[x]`
- `[Gap]` items here are frequent bug sources — prefer tightening the spec over relying on "obvious" behavior
- Any divergence between "hard-fail, no artifact" (FR-016) and "artifact-with-warning, status=failure" (FR-003, FR-018, FR-006) must be explicit, not contextual
- `[Ambiguity]` markers flag phrasing that a conscientious reader could interpret two ways; resolve before planning

## Resolution notes (2026-04-23)

All 50 items closed after the `/speckit.analyze` remediation pass that landed the 12-finding fix set (commit `9125af3`). Most items are directly pinned in the spec; the rest are pinned in adjacent feature artifacts that the reviewer sees alongside the spec. Soft resolutions reviewers should be aware of:

- **CHK006** (error channel): stderr JSON envelope pinned in `contracts/cli-contract.md`, not in spec FR-016.
- **CHK018** (`lines < 2 AND blocks == 1`): no-warning behavior is the logical complement of FR-018's trigger — implicit, not explicit.
- **CHK028** (`not_implemented` vs `failure` for `paddleocr_vl`): Key Entities reserves `"not_implemented"` for Falcon sources; V3 never emits it, but the "never" is implicit.
- **CHK033** (FR-012 scope): `"any engine-specific workaround"` applies to abnormal workarounds (e.g., `enable_mkldnn=False`); normal config choices like `cpu_threads=1` are design constraints, not workarounds. Scope is clear by common meaning.
- **CHK038** (pivot cost): lives in research §R-010; FR-017 references research.
- **CHK046** (init-failure error message stability): deterministic by construction of the structured `EngineInitError` fields, but not spelled out in FR-004 / FR-016.
- **CHK047** (commit-note on status-shift without text diff): intentionally scoped by Clarifications Q3 — the regeneration commit body tracks `document_text` diffs only, not status-only shifts.

No residuals at any severity level.

---

## Session 2026-04-23 Append — Post-Clarify Round 3 (CHK051–CHK068)

**Purpose**: Validate failure-handling requirement quality after the Session 2026-04-23 clarifications (Q23 FR-010 broad halt, Q24 FR-021 strict-current-shape, Q25 zero-overlap out-of-scope) and the tail of Session 2026-04-22 Q16–Q19. Every item tests whether the failure path is specified correctly — NOT whether the code handles it.

### FR-010 Broad Halt Scope (Session 2026-04-23 Q23)

- [ ] CHK051 Is the FR-010 halt-on-any-non-zero rule explicitly enumerated across all three exit codes (`1` unexpected, `2` input_rejected, `3` internal_error), or does it still read like the original "FR-016 engine-init" case only? [Completeness, Spec §FR-010]
- [ ] CHK052 Is the encrypted-PDF handling path under FR-010 explicit — does exit `2` halt the sweep alongside exit `3`, per the Session 2026-04-23 Q23 resolution? [Clarity, Spec §FR-010 §Clarifications 2026-04-23]
- [ ] CHK053 Is the unexpected-exception handling (exit `1`) path under FR-010 explicit — does a per-document runtime exception halt the whole sweep? [Clarity, Spec §FR-010]
- [ ] CHK054 Does the spec reconcile the broadened FR-010 halt rule with the older "FR-016 engine-init failure" phrasing so a reader doesn't see them as competing halt criteria? [Consistency, Spec §FR-010 §FR-016]
- [ ] CHK055 Is the rollback guidance for a halted sweep explicit — "do NOT commit partial baselines; git-discard and re-run from the top after root cause is fixed"? [Clarity, Spec §FR-010]
- [ ] CHK056 Is the FR-010 halt rule's interaction with the quickstart §5 `set -e` bash loop explicit, or is `set -e` assumed to be self-describing? [Traceability, Spec §FR-010]
- [ ] CHK057 Does the spec cover the case where a document exits `0` but writes an artifact with `ingestion_sources.paddleocr_vl.status == "failure"` — does the sweep continue normally, and is that intent explicit? [Coverage, Spec §FR-010 §FR-003]

### Zero-Overlap Edge Case (Session 2026-04-23 Q25)

- [ ] CHK058 Is the zero-overlap edge case (`lines > 0 AND blocks > 0 AND no bbox overlap`) declared out-of-scope with a specific future-category name (e.g., `[orphan_ocr_lines]`)? [Completeness, Spec §Edge Cases §Clarifications 2026-04-23]
- [ ] CHK059 Is the out-of-scope declaration explicit that the artifact is STILL written (schema-valid) rather than treated as a failure that halts the sweep? [Clarity, Spec §Edge Cases §FR-010]
- [ ] CHK060 Is the future-slice trigger criterion for introducing `[orphan_ocr_lines]` quantified (e.g., "corpus surfaces condition on ≥ 1 document"), or left unquantified? [Gap, Spec §Edge Cases]
- [ ] CHK061 Is the interaction between the zero-overlap case and FR-018's `[suspicious_single_block]` warning explicit — if both trigger conditions match (single block, lines ≥ 2, but no overlap), which warnings fire? [Coverage, Spec §Edge Cases §FR-018]

### FR-016 Hard-Fail Error Envelope Determinism

- [ ] CHK062 Is the FR-016 engine-init hard-fail error envelope (stderr JSON with `kind="engine_init_failed"`) required to be deterministic across runs given the same missing weight — so CI assertions on stderr content are reliable? [Coverage, Spec §FR-016 §FR-004]
- [ ] CHK063 Does the spec cover the case where FR-016 fires under the broadened FR-010 halt rule (i.e., FR-016 is one of the halting failure modes, not the only one)? [Consistency, Spec §FR-016 §FR-010]

### New Edge Cases Surfaced During Analyze/Clarify

- [ ] CHK064 Is the failure mode for `--write-page-images` when disk is full specified — does it affect the artifact's success state, or is PNG failure silently ignored? [Edge Case, Gap, Spec §FR-022]
- [ ] CHK065 Is the sweep's behavior when the corpus contains a folder with no `source.pdf` (labeling mistake) specified — does the CLI exit `2` and halt, or skip? [Edge Case, Gap, Spec §FR-010]
- [ ] CHK066 Does the spec require the CLI to identify which exit-code reason (`1` / `2` / `3`) triggered the halt before halting the sweep, so re-run diagnosis is direct? [Clarity, Spec §FR-010]

### Recovery and Re-Run Workflow

- [ ] CHK067 Is the "no partial baselines committed" guarantee enforced by operational practice (halt-then-don't-commit) rather than a code-level check — and is that trade-off explicit? [Clarity, Spec §FR-010]
- [ ] CHK068 Is the triage path after a halt documented well enough that a new contributor can re-run without consulting the PRD — i.e., is the failure-triage path self-contained in spec + research? [Coverage, Spec §FR-010 §FR-016]
