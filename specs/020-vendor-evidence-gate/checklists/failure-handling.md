# Failure-Handling Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Release-gate validation that every failure mode (CPU/stub
warn-and-proceed, GPU bind failure, empty/malformed input, gate-rule
non-determinism, fallback conflict, quality-gate failure, deferred GPU
verification) has explicit, deterministic, operator-visible behavior in the
spec. Every item validates the **requirements**, not the implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + ops/oncall reviewer)

## Warn-and-Proceed on CPU / Stub

- [x] CHK001 Is the warn-and-proceed behavior pinned to exactly three actions — (a) emit a clear stderr warning, (b) perform no behavior change, (c) exit with the same status as the no-flag run — rather than described as "graceful degradation"? [Clarity, Spec §FR-013 §SC-004]
- [x] CHK002 Is the warning's grep-able marker (`--evidence-gate-skip-fallback ignored:`) pinned as a literal substring so a reviewer can search for it in CI logs? [Measurability, R-020.12 / module-invariants.md MI-22]
- [x] CHK003 Is the rule "exactly ONE stderr line is emitted" stated, not just "a warning is emitted"? [Clarity, module-invariants.md MI-22]
- [x] CHK004 Are the no-warn conditions enumerated (opt-in unset; GPU profile + non-OCR-only strategy; GPU profile + OCR-only but no FR-005 trigger) so spurious warnings are forbidden? [Completeness, R-020.12 §The warn fires only when...]
- [x] CHK005 Is "silent ignore" explicitly named as NOT acceptable, so a future maintainer cannot weaken the contract by suppressing the warn? [Clarity, Spec §FR-013 §Edge Cases]
- [x] CHK006 Is "rejection with non-zero exit" explicitly named as NOT acceptable for this flag/profile combination, so a future maintainer cannot harden the contract by failing the run? [Clarity, Spec §FR-013 §Edge Cases]
- [x] CHK007 Does the spec state that the same exit code MUST be produced with vs. without the flag on a CPU profile (i.e., the warn does NOT change the exit code)? [Clarity, module-invariants.md MI-23]
- [x] CHK008 Is the rule "the four `run_summary` evidence-gate fields are still emitted under warn-and-proceed (the gate itself runs on CPU per FR-014)" stated, so the warn does not mask the always-emit invariant? [Consistency, R-020.12 / Spec §FR-014]

## GPU Bind Failure on Engaged Behavior

- [x] CHK009 Is the rule "GPU bind failure when a US4 behavioral shape is selected MUST fail fast (no silent CPU fallback)" stated as a hard requirement? [Clarity, Spec §Edge Cases]
- [x] CHK010 Does the spec require the exit reason to identify the active `evidence_gate_id` AND the active US4 shape identifier so operators can diagnose without re-instrumentation? [Completeness, Spec §Edge Cases]
- [x] CHK011 Is the carry-forward of feature 015 FR-008 / feature 017 FR-007 / feature 018 / feature 019 "no silent CPU fallback after `ppstructurev3@gpu` is selected" stated explicitly, not assumed by reference? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK012 Does the spec define what state the four `run_summary` evidence-gate fields take on a fail-fast GPU bind error (emitted with defaults? not emitted at all? partial?), so a downstream consumer is not surprised? [Gap, Spec §Edge Cases / R-020.10]

## Empty or Degenerate Input

- [x] CHK013 Is the rule "empty page-1 header band ⇒ all five signals at their negative level" stated explicitly so a near-blank page has a deterministic disposition (`insufficient`)? [Completeness, R-020.3 / R-020.5 / data-model.md §2]
- [x] CHK014 Is the rule "`pages[0]` is empty (zero blocks/boxes) ⇒ band is empty ⇒ all five signals at their negative level" called out as a distinct case from the empty-band case? [Completeness, R-020.5]
- [x] CHK015 Does the spec define behavior when `preprocess_output.json` has zero pages (rather than an empty page 1) — does the gate raise, fall through, or emit defaults? [Gap, R-020.5 / data-model.md §10]
- [x] CHK016 Does the spec define behavior when `preprocess_output.json` is malformed (e.g., missing required keys, wrong types) — does the gate raise, log, or fall through? [Gap, data-model.md §10 / module-invariants.md MI-2]
- [x] CHK017 Does the spec define behavior for a document with only footer evidence (no header band content) — explicitly named as falling through to `insufficient` and the legacy feature-019 behavior, "a conservative miss that is NOT a regression"? [Completeness, Spec §Clarifications Q4 / Spec §FR-001]
- [x] CHK018 Does the spec define behavior for multi-page documents where vendor identity appears only on pages 2..N — explicitly named as out-of-scope and falling through to `borderline` or `insufficient`? [Completeness, Spec §FR-001 §Clarifications Q4]

## Gate-Rule Non-Determinism (Regression Failure Modes)

- [x] CHK019 Is "the gate decision becomes non-deterministic or non-re-derivable from `preprocess_output.json` alone" named as a condition that preserves the legacy default? [Clarity, Spec §Edge Cases §Conditions under which the legacy default is preserved]
- [x] CHK020 Is the failure mode "recorded decision does NOT match re-derived decision" defined as a regression, not as a warning? [Clarity, evidence-gate-rule.md §Re-derivability guarantee / Spec §SC-002]
- [x] CHK021 Is "downstream-contract conflict where the gate or its behavioral effect would alter `preprocess_output.json` or any canonical artifact" named as a legacy-default-preserving failure mode? [Completeness, Spec §Edge Cases]
- [x] CHK022 Is "the team makes no promotion decision at landing" named as a non-failure case that ALSO keeps the legacy default — distinguishing inaction from failure? [Clarity, Spec §Edge Cases]
- [x] CHK023 Are these five legacy-default-preserving conditions enumerated explicitly (quality-gate failure / non-determinism / contract conflict / GPU bind failure / no promotion decision) so a future reviewer can audit which path applies? [Completeness, Spec §Edge Cases]

## Fallback Counter Conflict

- [x] CHK024 Is the rule "the gate decision MUST NOT change or mask either `region_strategy_fallback_count` or `ocr_only_fallback_count`" stated as a hard separation? [Clarity, Spec §Edge Cases]
- [x] CHK025 Is the rule "either counter MUST NOT change the gate decision" stated as the reverse-direction separation? [Completeness, Spec §Edge Cases]
- [x] CHK026 When feature 019's OCR-only fast lane fell back to PPStructureV3, is the rule "the gate runs on the resulting PPStructureV3 `preprocess_output.json` and emits whatever decision the signals imply" stated so the post-fallback gate evaluation has a pinned reference file? [Clarity, Spec §Edge Cases / R-020.7]
- [x] CHK027 Does the spec state that `evidence_gate_suppressed_fallback_count` and `ocr_only_fallback_count` are mutually exclusive per document (a suppressed document does NOT increment the latter; a fallen-back document does NOT increment the former)? [Consistency, R-020.7 / R-020.8 / cli-contract.md §Activation matrix]

## Borderline-Triggers-Behavior Failure Mode

- [x] CHK028 Is "only `sufficient` MAY trip the optional US4 behavioral effect" stated as unconditional regardless of which shape `/speckit.clarify` selected? [Clarity, Spec §FR-009 §SC-011 §Edge Cases]
- [x] CHK029 Is "borderline gate decision triggers behavioral effect" explicitly named as a forbidden behavior — i.e., a regression to detect, not just a default to avoid? [Clarity, Spec §Edge Cases]
- [x] CHK030 Does the spec define what happens on the unit-test surface if a future implementation accidentally allows `borderline` or `insufficient` to trip suppression (i.e., the test that catches this regression is named)? [Measurability, module-invariants.md MI-14 / Plan §test_evidence_gate_suppress_predicate.py]

## CPU/Stub Isolation Failure Mode

- [x] CHK031 Is the rule "no CPU code path may import GPU-only gate or behavioral-shape code" stated as a structural closure? [Clarity, Spec §US5 §FR-014]
- [x] CHK032 Is the verification mechanism (imports MUST be guarded so a host without Paddle GPU can run the default suite) named so the closure is testable? [Measurability, Spec §FR-014 §SC-005 / module-invariants.md MI-4 / MI-5]
- [x] CHK033 Does the spec define what happens if a CPU/stub run accidentally imports a GPU-only module — explicitly named as a regression (import-time failure on a no-GPU host) rather than a runtime error? [Completeness, Spec §FR-014]
- [x] CHK034 Is the rule "signal-set + gate-decision code MUST be importable and runnable on CPU and stub-adapter execution paths" stated as a hard requirement, not as a target? [Clarity, Spec §FR-014]

## Quality-Gate Failure (FR-016 Promotion Block)

- [x] CHK035 Is the rule "promotion that fails the gate is rejected; the legacy non-behaving default stays in place" stated as a hard requirement, not as guidance? [Clarity, Spec §US7 §FR-016]
- [x] CHK036 Is the parity condition pinned as `candidate_metric >= legacy_metric` for BOTH metrics, with no tolerance allowed? [Clarity, Spec §FR-016 / R-020.14]
- [x] CHK037 Are the two metrics enumerated by name (per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json` AND per-document pass count per `docs/stage1-vendor-identity/scoring.md`) so a single-metric promotion is impossible to slip in? [Completeness, Spec §FR-016 §SC-008]
- [x] CHK038 Is "the candidate stays selectable only via explicit configuration after a failed promotion" stated so a rejected candidate is not silently removed? [Clarity, Spec §US7 AC#3 §FR-018]
- [x] CHK039 Is the rule "promotion of a new default MUST NOT remove the legacy non-behaving configuration as a selectable option" stated as a forward-compatibility invariant? [Clarity, Spec §FR-018 §Edge Cases §Operator overrides]

## Deferred GPU Verification (FR-026)

- [x] CHK040 Is the deferral mechanism (mark as `@pytest.mark.gpu`, capture in `tasks.md`, capture in `quickstart.md` Appendix B) pinned, so deferral cannot be silent? [Clarity, Spec §FR-026 / R-020.15]
- [x] CHK041 Is the CPU-safe deferral floor enumerated by test file name (signal-set, decision-table, opt-in resolution, coordinate filter, warn-and-proceed, corpus-run aggregation, run_summary schema bump, legacy byte-identity) so a reviewer can confirm the floor is intact? [Completeness, R-020.15 / Plan §Testing]
- [x] CHK042 Is the rule "GPU-marked tests are skipped via `@pytest.mark.gpu` rather than failed" stated so a missing-GPU host does not turn into a red CI? [Clarity, Spec §FR-024 §SC-005]
- [x] CHK043 Is "the deferral MUST NOT block landing the CPU-safe implementation" stated as a permissive rule for merge, not just for verification? [Clarity, Spec §FR-026]
- [x] CHK044 Is the rule "the deferred items MUST be captured in `tasks.md` and quickstart so the verification cannot be quietly skipped" stated as a hard requirement, not as a recommendation? [Clarity, Spec §FR-026 / R-020.15]

## Operator-Visibility Failure Mode

- [x] CHK045 Is "absence of any of the four new `run_summary` fields on a run of the new binary" defined as a regression signal, not as a degraded mode? [Clarity, Spec §SC-003 §US3 AC#3]
- [x] CHK046 Does the spec require operator-visibility of every suppression event (`evidence_gate_suppressed_fallback_count >= 1` on the run + the document's `evidence_gate_documents` entry recording `decision: "sufficient"`) so a silent suppression is impossible? [Completeness, Spec §US4 AC#1 §SC-003]
- [x] CHK047 Does the spec define what an operator should do if a `run_summary` shows `evidence_gate_id != "v1"` at landing (i.e., is it a regression, a future-preset signal, or a misconfiguration)? [Gap, R-020.2 / FR-005]

## Forward-Compatibility Failure Modes

- [x] CHK048 Is the rule "future preset additions MUST require both a new registry entry AND a new contract document AND a new selection flag (when registry size grows beyond one)" stated so a partial addition is forbidden? [Completeness, evidence-gate-rule.md §Closed-vocabulary preset registry]
- [x] CHK049 Does the spec define what happens if the v1 thresholds change without a new `evidence_gate_id` value (explicitly named as a determinism violation and a regression)? [Clarity, evidence-gate-rule.md §Versioning policy]

## Cross-Reference to Prior-Feature Failure Patterns

- [x] CHK050 Is the precedent "mirrors feature 016 FR-010 / feature 017 FR-013 / feature 018 FR-014 / feature 019 FR-013" called out for the warn-and-proceed rule, so a reviewer can confirm the pattern is consistent? [Consistency, Spec §FR-013]
- [x] CHK051 Is the precedent "feature 016 FR-014 / feature 017 FR-024 / feature 018 FR-025 / feature 019 FR-025" called out for the GPU-verification deferral path? [Consistency, Spec §FR-026 / R-020.15]
- [x] CHK052 Is the precedent "feature 017 R-017.10 / feature 018 R-018.11 / feature 019 R-019.x" called out for the two-metric quality-gate rule? [Consistency, R-020.14]

## Verifiability of Failure-Handling Claims

- [x] CHK053 For every named failure mode (warn-and-proceed, GPU bind fail-fast, empty band, malformed input, borderline-suppression, quality-gate failure, deferred GPU verification), is there a named test or CI check that exercises it? [Measurability, Plan §Testing / module-invariants.md]
- [x] CHK054 Is the verification command for the warn line (`2>&1 | grep -F -- "--evidence-gate-skip-fallback ignored:"`) named in the contract so a reviewer can grep for it manually? [Measurability, cli-contract.md §Verification]
- [x] CHK055 Is the verification command for the always-emit invariant (`jq -e '.evidence_gate_id'` and equivalents for the other three fields) named so a reviewer can verify a captured `run_summary` line manually? [Measurability, run-summary-schema.md §Verification]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality**, not implementation correctness
