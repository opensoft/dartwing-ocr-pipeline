# Determinism Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Release-gate validation that every requirement in the spec
preserves the project's deterministic-control constitution rule — signal
computation, gate decision, suppression predicate, evaluation order, and
operator re-derivation are all pure functions of `preprocess_output.json`
content with byte-identical output across hosts and reruns. Every item
validates the **requirements**, not the implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + constitution-rule owner)

## Pure-Function Closure of Signal Computation

- [x] CHK001 Is the rule "each FR-001 signal MUST be a pure function over `preprocess_output.json` content" stated as a hard requirement, not as guidance? [Clarity, Spec §FR-001 §FR-027]
- [x] CHK002 Is the prohibition on consulting extraction, classification, routing, or vendor-identity model output stated for the signal-set surface as a whole, not just per-signal? [Completeness, Spec §FR-001]
- [x] CHK003 Is the prohibition repeated as an architectural closure (e.g., the gate module's type signature accepts only `preprocess_output` dicts) so accidental coupling is structurally impossible? [Clarity, module-invariants.md MI-1 / MI-2 / MI-3]
- [x] CHK004 Is the rule "no learned classifier, no statistical model, no extraction-model inputs" stated as a permanent closure, not as a current limitation? [Clarity, Spec §FR-027 §Out of Scope]
- [x] CHK005 Is "future ML-derived signals require a separate feature and a separate constitutional review" stated explicitly, so the closure cannot be relaxed by a follow-on PR? [Clarity, Spec §FR-027]
- [x] CHK006 Is the rule "no file I/O outside the input dict, no network, no model call" stated at module-load granularity (not just at evaluation-time)? [Completeness, module-invariants.md MI-1]
- [x] CHK007 Does the spec state that `import preprocessing.evidence_gate` MUST succeed on a host with no Paddle installed? [Measurability, module-invariants.md MI-4 / MI-5]

## Byte-Identical Reproducibility

- [x] CHK008 Is the rule "two runs on the same `preprocess_output.json` produce byte-identical signal values" stated for every signal in FR-001, not for the signal set in aggregate? [Clarity, Spec §SC-001 §US1 AC#1]
- [x] CHK009 Is byte-identity required across hosts (different OS, different container) and not just across reruns on the same host? [Completeness, Spec §SC-001 §US1 AC#2]
- [x] CHK010 Is byte-identity required across preprocessing strategies (feature 018 `full-page` / `header-first-v1` and feature 019 `ppstructurev3` / `ocr-only-v1`) when the `preprocess_output.json` contents differ measurably, with the boundary stated as "attributable to a measurable content difference, not to the strategy identifier"? [Clarity, Spec §FR-002 §US1 AC#3]
- [x] CHK011 Is the verification surface for byte-identity pinned (e.g., "at least one re-run on the same host and one run on a different host or container"), not left as "verified across runs"? [Measurability, Spec §SC-001]
- [x] CHK012 Does the spec require NFKC Unicode normalization before tokenization so signal values are stable across platforms and locales? [Completeness, R-020.3 / module-invariants.md MI-9]
- [x] CHK013 Is the rule "numeric fields MUST be finite (no `NaN`, no `Infinity`)" stated for `ocr_detection_confidence_mean` and `header_band_token_density`? [Completeness, data-model.md §2]

## Coordinate-Filter Determinism

- [x] CHK014 Is the y-coordinate threshold pinned to a specific fraction (`Y_THRESHOLD_FRACTION = 0.25`) rather than left as "approximately 25%"? [Clarity, R-020.5 / Spec §Clarifications Q4]
- [x] CHK015 Is the comparison operator pinned (`bbox_top_y / page_height < 0.25` — strict-less-than) so the boundary token disposition is unambiguous? [Clarity, R-020.5]
- [x] CHK016 Is the dimension-invariance property (fraction-based filter works identically on US Letter / A4 / Legal) stated as a determinism property, not just a design choice? [Clarity, R-020.5]
- [x] CHK017 Is the multi-page-document rule "tokens on `pages[1..N]` are NOT considered by any of the five signals" stated explicitly, so the multi-page edge case has a pinned answer? [Completeness, R-020.5]
- [x] CHK018 Is the empty-band fallback for every signal pinned to its negative level (`vendor_name_candidate_count=0`, `header_band_token_density=0`, `ocr_detection_confidence_mean=0.0`, `business_suffix_present=False`, `tax_id_shaped_present=False`)? [Completeness, R-020.3 / data-model.md §2]
- [x] CHK019 Is `Y_THRESHOLD_FRACTION` explicitly described as immutable at module load (`Final[...]`), not operator-configurable via env var? [Clarity, R-020.5 / data-model.md §7]

## Regex Pattern Determinism

- [x] CHK020 Is each of the three regex patterns pinned by literal source code (`BUSINESS_SUFFIX_RE`, `TAX_ID_EIN_RE`, `TAX_ID_VAT_RE`) rather than described by example tokens? [Clarity, R-020.4 / data-model.md §6]
- [x] CHK021 Is the case-sensitivity decision per pattern justified explicitly (business-suffix case-insensitive; tax-id patterns case-sensitive) so it is not silently flipped later? [Clarity, R-020.4]
- [x] CHK022 Is the rule "matching is whole-token via `\b` boundaries, not substring" stated so partial-match drift is forbidden? [Clarity, R-020.4 / data-model.md §6]
- [x] CHK023 Is the rule "patterns MUST compile at module load (a regex compilation error is a developer error, not a runtime error)" stated as a hard contract? [Completeness, data-model.md §6]
- [x] CHK024 Is the stop-word set for `vendor_name_candidate_count` pinned as a `frozenset[str]` constant with the exact members enumerated (`"INVOICE"`, `"BILL"`, `"TAX"`, `"DATE"`, `"PAGE"`, `"NUMBER"`, `"TOTAL"`, `"AMOUNT"`, `"DUE"`, `"PAYMENT"`, `"FROM"`, `"TO"`), not described as "common invoice header words"? [Clarity, R-020.3 / data-model.md §8]
- [x] CHK025 Is the case-folded comparison for the stop-word set stated explicitly so locale-dependent casing rules do not affect determinism? [Clarity, data-model.md §8]

## V1 Decision Table Determinism

- [x] CHK026 Is the v1 decision logic stated as a closed boolean expression with no implicit defaults or randomness, so two implementations of the same expression cannot disagree? [Clarity, R-020.6 / evidence-gate-rule.md]
- [x] CHK027 Is every threshold (`DENSITY_THRESHOLD = 8`, `CONFIDENCE_THRESHOLD = 0.70`) pinned to a specific value with the inclusive-on-the-high-side comparison documented? [Clarity, R-020.6 / evidence-gate-rule.md]
- [x] CHK028 Are the 32 truth-table rows enumerated (3 fire `sufficient`, 1 fires `insufficient`, 28 fire `borderline`) so a reviewer can confirm the decision boundary is fully specified? [Completeness, evidence-gate-rule.md §Decision table]
- [x] CHK029 Is the rule "thresholds are NOT operator-tunable knobs; a new preset is required to change them" stated as a permanent closure? [Clarity, R-020.5 / R-020.6 / evidence-gate-rule.md §Versioning]
- [x] CHK030 Is the closed-vocabulary constraint on `decision` (`sufficient` / `borderline` / `insufficient`) stated at every layer (gate-rule body, run_summary field, per-document record) so a fourth state cannot leak in via any surface? [Consistency, Spec §US2 / module-invariants.md MI-26 / data-model.md §3 §4]
- [x] CHK031 Is the rule "adding a fourth state is a code change plus a new explicit state value, not a runtime parameter" stated as a permanent closure? [Clarity, Spec §FR-004 §US2]

## Operator Re-Derivability

- [x] CHK032 Is the rule "the recorded gate decision MUST be re-derivable from the recorded signal values plus the documented decision table without re-running the binary" stated explicitly, not as an implication? [Clarity, Spec §SC-002 §SC-012 §US2 AC#4]
- [x] CHK033 Is the re-derivation procedure documented step-by-step so a non-author can verify a recorded decision? [Completeness, evidence-gate-rule.md §Re-derivation procedure]
- [x] CHK034 Is the rule "if the re-derived decision does NOT match the recorded decision, it is a determinism violation and a regression" stated as a hard failure mode? [Clarity, evidence-gate-rule.md §Re-derivability guarantee / Spec §FR-001 §SC-002]
- [x] CHK035 Are at least two worked boundary examples (e.g., name+density+confidence+suffix → `sufficient`; blank page → `insufficient`) included so the re-derivation procedure is testable on the document alone? [Measurability, evidence-gate-rule.md §Boundary cases]
- [x] CHK036 Is the FR-016 quality-gate join (per-document `document_id` matched between `evidence_gate_documents` and `evaluation_run_summary.json`) deterministic across reruns? [Consistency, R-020.11 / Spec §FR-016]

## Evaluation-Order Determinism (R-020.7)

- [x] CHK037 Is the rule "the recorded decision is the gate evaluation over the FINAL `preprocess_output.json`" stated as a hard requirement, not as a default? [Clarity, R-020.7 / module-invariants.md MI-10]
- [x] CHK038 Are the four per-document evaluation-count cases (non-OCR-only / OCR-only no-opt-in / OCR-only opt-in no-trigger / OCR-only opt-in trigger-suffices / OCR-only opt-in trigger-falls-back) each named with their evaluation count pinned (1 or 2 evaluations)? [Completeness, R-020.7]
- [x] CHK039 Is the rule "when fallback fires after a non-suppressing candidate evaluation, the gate is evaluated TWICE (once on candidate for suppression decision, once on post-fallback for recorded decision)" stated explicitly? [Clarity, R-020.7 / module-invariants.md MI-11]
- [x] CHK040 Is the candidate-evaluation result described as "used only for the suppression decision and NOT recorded directly on `run_summary`" so two evaluations do not leak two records? [Clarity, R-020.7]

## Suppression-Predicate Determinism

- [x] CHK041 Is the suppression predicate stated as a four-conjunct pure function (`preprocess_strategy_id == "ocr-only-v1"` AND `fr_005_trigger_would_fire` AND `opt_in_active` AND `candidate_gate_decision == "sufficient"`)? [Clarity, R-020.8 / module-invariants.md MI-13]
- [x] CHK042 Is the rule "`borderline` and `insufficient` candidate gate decisions MUST NEVER trigger suppression, regardless of opt-in or strategy" stated as an unconditional invariant? [Clarity, Spec §FR-009 §SC-011 / module-invariants.md MI-14]
- [x] CHK043 Is the increment rule for `evidence_gate_suppressed_fallback_count` pinned as "exactly `1` per document where suppression fires, never otherwise"? [Clarity, R-020.8 / module-invariants.md MI-15]
- [x] CHK044 Does the spec define the truth-table coverage requirement for the suppression predicate (all 16 truth-table rows tested) so corner cases cannot silently disagree? [Measurability, module-invariants.md MI-13]
- [x] CHK045 Is the rule "the predicate is pure — its inputs come from preprocessing-pass state, no model in the loop" stated so accidental coupling is forbidden? [Clarity, R-020.8]

## CLI/Env-Var Resolution Determinism

- [x] CHK046 Is the resolution function `resolve_evidence_gate_skip_fallback(cli_value, env)` stated as a pure function of its arguments, with no global state? [Clarity, R-020.1 / data-model.md §10]
- [x] CHK047 Is the precedence rule deterministic (CLI wins; empty-string env = unset; truthy/falsy vocabulary closed)? [Clarity, R-020.1 / cli-contract.md §Precedence]
- [x] CHK048 Does the spec define behavior for an unrecognized env-var value (rejection via the existing `_PRESET_ENV_VAR` helpers) so silent acceptance is forbidden? [Completeness, R-020.1 / cli-contract.md §Exit codes]

## Module-Level Immutability

- [x] CHK049 Are all module-level constants (`Y_THRESHOLD_FRACTION`, `DENSITY_THRESHOLD`, `CONFIDENCE_THRESHOLD`, `BUSINESS_SUFFIX_RE`, `TAX_ID_EIN_RE`, `TAX_ID_VAT_RE`, `VENDOR_NAME_STOP_WORDS`, `EVIDENCE_GATE_ID_V1`, `EVIDENCE_GATE_ID_DEFAULT`, `EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR`) declared `Final[...]` (or equivalent) at module load? [Completeness, module-invariants.md MI-8 / data-model.md Appendix A] *(B post-review: `EVIDENCE_GATES` registry collapsed to constants + `decide_for_gate` dispatch — the closed-vocabulary discipline now lives in the dispatch guard.)*
- [x] CHK050 Is the rule "unknown gate id is a developer error" enforced by `decide_for_gate` / `evaluate_evidence_gate` raising `KeyError` for any id other than `"v1"`? [Clarity, module-invariants.md MI-25]
- [x] CHK051 Is the rule "the gate is stateless at module level; no in-process mutable globals" stated as an invariant? [Clarity, data-model.md §10]

## Determinism Boundary with Adjacent Features

- [x] CHK052 Is the rule "the gate MUST NOT alter, suppress, or shadow feature 018's `region_strategy_fallback_count` or feature 019's `ocr_only_fallback_count`" stated as a hard requirement so two surfaces remain independent and additive? [Clarity, Spec §FR-023 §Edge Cases]
- [x] CHK053 Is the rule "feature 008's deterministic routing surface is unchanged by this feature" stated so the constitution's "consensus and routing are never delegated to a model" rule cannot be weakened transitively? [Clarity, Spec §FR-028 §Out of Scope]
- [x] CHK054 Is feature 019's FR-005 fallback trigger logic explicitly stated as unchanged (the gate decision plus the trigger together MUST deterministically and unambiguously decide whether the document falls back)? [Consistency, Spec §FR-007 §Out of Scope]

## Verifiability of Determinism Claims

- [x] CHK055 For every byte-identity claim (signal values, decision, counter), is there a named test that verifies it on CPU before merge (i.e., not deferred behind GPU)? [Measurability, R-020.15 §CPU-safe deferral floor]
- [x] CHK056 Does the spec name the verification path for cross-host determinism (e.g., devcontainer vs. workstation; container vs. host) so SC-001's "different host or container" is not left as a thought experiment? [Measurability, Spec §SC-001]
- [x] CHK057 Is the verification mechanism for the closed three-state vocabulary (mypy / pyright `Literal[...]` enforcement + runtime tests on boundary thresholds) documented so a reviewer can confirm the type-level closure? [Measurability, module-invariants.md MI-26]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality**, not implementation correctness
