# Evidence-Gate Policy Checklist: v1 Decision Table, Opt-In Promotion, And Quality-Gate Evidence

**Purpose**: Release-gate validation that the spec pins the v1 evidence-gate
policy (signal definitions, thresholds, decision-table cells, opt-in
promotion mechanics, two-metric quality-gate evidence, deferred-GPU
verification path) with the rigor needed for a future preset author to
re-derive every decision from this document alone. Every item validates
the **requirements**, not the implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + gate-policy owner + future preset author)

## Closed-Vocabulary Preset Registry

- [x] CHK001 Is the closed-vocabulary size at landing pinned (exactly one valid `gate_id`: `"v1"`) so a reviewer knows what to expect from `decide_for_gate` / `evaluate_evidence_gate`? [Clarity, R-020.2 / evidence-gate-rule.md §Closed-vocabulary preset registry] *(B post-review: the original dataclass + `EVIDENCE_GATES` dict was collapsed to module constants + `decide_for_gate(gate_id, signals)` dispatch — same closed vocabulary, flatter shape.)*
- [x] CHK002 Is the rule "adding a new preset requires (1) a new `_v2_decide` function + additive branch in `decide_for_gate` / `evaluate_evidence_gate`, (2) a new `contracts/evidence-gate-rule.md` section, (3) a new selection flag, (4) an entry in the FR-005/FR-007 closed-vocabulary documentation" stated so a partial addition is forbidden? [Completeness, evidence-gate-rule.md §Closed-vocabulary preset registry]
- [x] CHK003 Is the rule "an unknown `evidence_gate_id` value is a developer error, not a runtime preset-selection error" stated so the absence of an `UnknownPresetError` extension is explained? [Clarity, evidence-gate-rule.md §Closed-vocabulary preset registry]
- [x] CHK004 Is `EVIDENCE_GATE_ID_DEFAULT = EVIDENCE_GATE_ID_V1 = "v1"` pinned as the active-at-landing identifier, with the lineage to feature 017's `module_set_id` versioning called out? [Consistency, R-020.2]
- [x] CHK005 Is the `evidence_gate_id` value constrained to a human-readable string (not an opaque numeric hash) and the rationale documented? [Clarity, R-020.2 / Spec §FR-010]

## Signal Definitions (FR-001 Closed Set of Five)

- [x] CHK006 Is each of the five signal names (`vendor_name_candidate_count`, `header_band_token_density`, `ocr_detection_confidence_mean`, `business_suffix_present`, `tax_id_shaped_present`) pinned with its type, range, and definition? [Completeness, R-020.3 / data-model.md §2]
- [x] CHK007 Is the vendor-name-candidate heuristic stated as a four-clause conjunction (length, casing, not-pure-number, not-in-stop-word-set), not as "a vendor-name pattern"? [Clarity, R-020.3]
- [x] CHK008 Is the stop-word set enumerated (`INVOICE`, `BILL`, `TAX`, `DATE`, `PAGE`, `NUMBER`, `TOTAL`, `AMOUNT`, `DUE`, `PAYMENT`, `FROM`, `TO`) with case-folded comparison stated? [Completeness, R-020.3 / data-model.md §8]
- [x] CHK009 Is the tokenization rule pinned (whitespace-based on the recognized text strings emitted on each block/box, with NFKC Unicode normalization first)? [Clarity, R-020.3 / module-invariants.md MI-9]
- [x] CHK010 Is `ocr_detection_confidence_mean = 0.0` for an empty band stated explicitly so the no-data case is unambiguous? [Completeness, R-020.3 / data-model.md §2]
- [x] CHK011 Is the rule "aggregate mean (not median) for confidence" pinned with the rationale (consistency with feature 019 R-019.6's FR-005 trigger threshold)? [Clarity, R-020.3 §Alternatives considered]
- [x] CHK012 Is the rule "telephone/email/postal-address-shaped tokens are NOT in this feature's scope" repeated at the FR-001 level so a reader cannot infer them from "a signal set over `preprocess_output.json`"? [Clarity, Spec §Clarifications Q2 §FR-001 / R-020.3 §Alternatives considered]

## Regex Patterns (R-020.4)

- [x] CHK013 Is the `BUSINESS_SUFFIX_RE` source pinned literally (`r"(?i)\b(LLC|Incorporated|Inc|Limited|Ltd|GmbH|S\.A\.S\.|S\.A\.|Corporation|Corp|Co\.)(?![\w-])"`) with each entity-suffix term enumerated? [Completeness, R-020.4 / data-model.md §6] *(A1 post-review: trailing `(?![\w-])` replaces `\b` so `.`-suffixed forms match at end-of-string AND hyphenated compounds like `Inc-related` are rejected; longer alternatives listed first.)*
- [x] CHK014 Is the inclusion of non-US suffixes (`GmbH`, `S.A.`, `S.A.S.`) justified explicitly (corpus may contain non-US invoices)? [Clarity, R-020.4]
- [x] CHK015 Is the `TAX_ID_EIN_RE` source pinned (`r"\b\d{2}-\d{7}\b"`) with the EIN shape (XX-XXXXXXX) documented? [Completeness, R-020.4 / data-model.md §6]
- [x] CHK016 Is the `TAX_ID_VAT_RE` source pinned (`r"\b[A-Z]{2}(?=[A-Z0-9]{2,12}\b)[A-Z0-9]*\d[A-Z0-9]*\b"`) with the EU canonical shape (country prefix + alphanumeric body containing at least one digit) documented and the known false-positive rate acknowledged? [Completeness, R-020.4] *(B2 post-review: the digit-required form rejects common all-letter invoice header words like `INVOICE` / `PAYMENT` / `NUMBER` / `BALANCE` that the prior `[A-Z]{2}[A-Z0-9]{2,12}` shape falsely matched.)*
- [x] CHK017 Is the case-sensitivity decision per pattern justified (business-suffix case-insensitive due to invoice variation; tax-id case-sensitive)? [Clarity, R-020.4]
- [x] CHK018 Is the rationale for rejecting UK NI / SSN patterns documented (PII risk + labeling-guide.md screening checklist), so this exclusion is not silently relaxed? [Clarity, R-020.4 §Alternatives considered]

## Coordinate Filter (R-020.5)

- [x] CHK019 Is the page-1 header band defined precisely (`pages[0]` AND `bbox_top_y / page_height < Y_THRESHOLD_FRACTION = 0.25`)? [Clarity, R-020.5 / data-model.md §7]
- [x] CHK020 Is the strict-less-than comparison documented so boundary tokens (exactly at the 0.25 line) are unambiguously in the page body, not the header? [Clarity, R-020.5]
- [x] CHK021 Is the coordinate-origin convention (top-left, y increases downward, units `pt`) named so a reader can trace the comparison without consulting the schema? [Completeness, R-020.5]
- [x] CHK022 Is the rationale for using a fraction (not an absolute point value) documented as dimension-invariance across US Letter / A4 / Legal? [Clarity, R-020.5]
- [x] CHK023 Is the rule "the y-fraction is plan-time pinned but kept as a named constant so a future preset (v2) can adjust it" stated so the constant's mutability boundary is clear (compile-time only, never runtime)? [Clarity, R-020.5]

## V1 Decision Table (R-020.6)

- [x] CHK024 Is the `sufficient` rule stated as the four-way conjunction `has_name AND has_density AND has_confidence AND (has_suffix OR has_tax_id)`, not as "all signals positive"? [Clarity, R-020.6 / evidence-gate-rule.md]
- [x] CHK025 Is the `insufficient` rule stated as the five-way negation `NOT has_name AND NOT has_density AND NOT has_confidence AND NOT has_suffix AND NOT has_tax_id`, not as "all signals negative"? [Clarity, R-020.6 / evidence-gate-rule.md]
- [x] CHK026 Is `borderline` stated as the residual (any combination not matching the other two rules)? [Clarity, R-020.6]
- [x] CHK027 Are the three precise thresholds (`DENSITY_THRESHOLD = 8`, `CONFIDENCE_THRESHOLD = 0.70`, `vendor_name_candidate_count >= 1`) pinned with units? [Completeness, R-020.6 / evidence-gate-rule.md]
- [x] CHK028 Is the inclusive-on-the-high-side comparison rule documented (boundary values of exactly `8` / `0.70` / `1` qualify as positive)? [Clarity, R-020.6 / evidence-gate-rule.md §V1 decision table]
- [x] CHK029 Is the 32-row truth table enumerated in full (with the row-counts 3/1/28 verifiable) so a reviewer can confirm no rule is missing? [Completeness, evidence-gate-rule.md §Decision table]
- [x] CHK030 Is the rationale for the `(has_suffix OR has_tax_id)` disjunction (vendor blocks legitimately have a suffix OR a tax-id, rarely both) documented? [Clarity, R-020.6 §Alternatives considered]
- [x] CHK031 Is the rationale for `DENSITY_THRESHOLD = 8` (empirical median over the 017/018/019 benchmark subset; calibration may revise upward in v2) documented? [Clarity, R-020.6 / evidence-gate-rule.md §Threshold rationale]
- [x] CHK032 Is the rationale for `CONFIDENCE_THRESHOLD = 0.70` (matches feature 019's R-019.6; intentionally higher than the 0.60 fallback threshold because `sufficient` is a stronger claim than "OCR good enough to keep") documented? [Clarity, R-020.6 / evidence-gate-rule.md §Threshold rationale]
- [x] CHK033 Is the rationale for `Y_THRESHOLD_FRACTION = 0.25` (per feature 018's header-first-v1 calibration) documented? [Clarity, evidence-gate-rule.md §Threshold rationale]

## Re-Derivation Procedure

- [x] CHK034 Is the step-by-step re-derivation procedure documented (compute five derivatives → evaluate `sufficient` rule → evaluate `insufficient` rule → residual `borderline`)? [Completeness, evidence-gate-rule.md §Re-derivation procedure]
- [x] CHK035 Is at least one worked example included so a non-author can verify a recorded decision against the documented table? [Measurability, evidence-gate-rule.md §Re-derivation procedure]
- [x] CHK036 Are the six boundary cases enumerated (single-token vendor name, vendor+suffix but low confidence, sparse band with suffix, completely blank page, name+density+confidence+suffix, name+density+confidence+tax-id) so reviewers see the decision boundary clearly? [Completeness, evidence-gate-rule.md §Boundary cases]
- [x] CHK037 Is the re-derivability guarantee (`r.decision == v1_decide(r.signals)`) stated as a hard invariant verified by a named test? [Measurability, evidence-gate-rule.md §Re-derivability guarantee / module-invariants.md MI-7]

## Opt-In Promotion Mechanics (FR-007 / FR-012)

- [x] CHK038 Is the opt-in default ("OFF on every profile at landing, including `ppstructurev3@gpu`") stated as a hard requirement? [Clarity, Spec §FR-012 / module-invariants.md MI-20]
- [x] CHK039 Is "promoting the opt-in to default-on requires passing the FR-016 quality gate AND a code change to flip the default" stated as a two-step gate? [Clarity, Spec §FR-016 / module-invariants.md MI-21]
- [x] CHK040 Is the rule "the opt-in is GPU-only by design" stated so a future maintainer cannot accidentally promote a CPU-side default change? [Clarity, Spec §FR-012 §Out of Scope]
- [x] CHK041 Is the rule "promotion of a new default MUST NOT remove the legacy non-behaving configuration as a selectable option" stated as a forward-compatibility invariant? [Clarity, Spec §FR-018]
- [x] CHK042 Does the spec define which combination of inputs triggers the opt-in (active flag/env-var resolution AND `preprocess_strategy_id == "ocr-only-v1"` AND FR-005 trigger fires AND gate decision `sufficient`)? [Completeness, R-020.8 / cli-contract.md §Activation matrix]

## Two-Metric Quality Gate (FR-016 / R-020.14)

- [x] CHK043 Is the two-metric requirement stated as a hard `AND` (both must be `>=` legacy), not as a `OR` (either one suffices)? [Clarity, Spec §FR-016 §SC-008 / R-020.14]
- [x] CHK044 Is metric 1 (per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json`) named and its source artifact pinned? [Completeness, Spec §FR-016 / R-020.14]
- [x] CHK045 Is metric 2 (per-document pass count per `docs/stage1-vendor-identity/scoring.md`) named and its source contract pinned? [Completeness, Spec §FR-016 / R-020.14]
- [x] CHK046 Is the parity condition `candidate_metric >= legacy_metric` pinned with no tolerance allowed (e.g., no `>= 0.98 * legacy`)? [Clarity, R-020.14 §Alternatives considered]
- [x] CHK047 Is the rule "both metrics MUST come from the existing evaluator outputs; no new metric is introduced" stated so a single-metric promotion path is forbidden? [Clarity, Spec §FR-016 / R-020.14]
- [x] CHK048 Is the corpus subset for evaluation pinned (the same fixed 5-doc subset features 017/018/019 used)? [Clarity, R-020.13 / Spec §FR-015]
- [x] CHK049 Is the rule "evidence MUST be recorded in this feature's research artifact alongside the candidate's `evidence_gate_id`" stated so the audit trail is permanent? [Clarity, Spec §FR-017]

## Benchmark (FR-015)

- [x] CHK050 Is the benchmark scope (legacy default + skip-fallback opt-in candidate, both on the same fixed 5-doc subset) pinned, not described abstractly? [Clarity, Spec §FR-015 / R-020.13]
- [x] CHK051 Are the four recorded benchmark fields enumerated ((a) per-document signal-set values, (b) per-document gate decision, (c) per-corpus distribution across three states, (d) per-corpus latency-or-quality delta vs. legacy)? [Completeness, Spec §FR-015]
- [x] CHK052 Is the rule "the FR-015 benchmark numbers land in `quickstart.md` Appendix A at landing" stated so the evidence has a pinned home? [Completeness, Plan §Storage]
- [x] CHK053 Is the rule "`evidence_gate_suppressed_fallback_count >= 1` on the benchmark for at least one fixture with opt-in active and a `sufficient` decision" stated as a measurable benchmark outcome? [Measurability, Plan §Performance Goals / Spec §SC-012]

## Suppression Predicate (R-020.8)

- [x] CHK054 Is the four-conjunct predicate (`preprocess_strategy_id == "ocr-only-v1"` AND `fr_005_trigger_would_fire` AND `opt_in_active` AND `candidate_gate_decision == "sufficient"`) pinned literally? [Clarity, R-020.8 / module-invariants.md MI-13]
- [x] CHK055 Is the rule "the predicate is pure; inputs come from preprocessing-pass state only; no model in the loop" stated so an accidental dependency on extraction output is impossible? [Clarity, R-020.8]
- [x] CHK056 Is the rule "`borderline` and `insufficient` MUST NEVER trigger suppression regardless of opt-in or strategy" stated unconditionally? [Clarity, Spec §FR-009 §SC-011 / module-invariants.md MI-14]
- [x] CHK057 Is the counter increment rule (`evidence_gate_suppressed_fallback_count` += exactly 1 per document where the predicate returns True, never otherwise) pinned? [Clarity, R-020.8 / module-invariants.md MI-15]
- [x] CHK058 Is the rejection of alternatives (gate module decides suppression directly; allow `borderline` to suppress under a separate opt-in; increment for every `sufficient` document not just suppression events) documented so the predicate cannot be silently weakened? [Completeness, R-020.8 §Alternatives considered]

## Evaluation Order (R-020.7)

- [x] CHK059 Is the rule "the recorded decision is the gate evaluation over the FINAL `preprocess_output.json`" stated explicitly? [Clarity, R-020.7 / module-invariants.md MI-10]
- [x] CHK060 Are the five per-document evaluation-count cases enumerated with their evaluation counts? [Completeness, R-020.7 §Per-document evaluation count]
- [x] CHK061 Is the rule "the candidate-output evaluation is used only for the suppression decision and is NOT recorded directly on `run_summary`" stated so two evaluations do not leak two records? [Clarity, R-020.7]
- [x] CHK062 Is the rejection of alternative evaluation orders (always record over candidate; evaluate twice on every doc; skip candidate evaluation and use a simpler proxy) documented? [Completeness, R-020.7 §Alternatives considered]

## Versioning Policy (Frozen at v1)

- [x] CHK063 Is the rule "any change to thresholds, decision-table cells, per-signal computation rules, or the FR-001 closed signal set requires a new `evidence_gate_id` value — never a runtime knob" stated as a permanent policy? [Clarity, evidence-gate-rule.md §Versioning policy]
- [x] CHK064 Is the mirror to feature 017's `module_set_id` / feature 018's `raster_profile_id` & `region_strategy_id` / feature 019's `preprocess_strategy_id` versioning called out for consistency? [Consistency, evidence-gate-rule.md §Versioning policy]
- [x] CHK065 Does the spec define what a future v2 preset author needs in order to land their preset (registry entry + contract document + selection flag + closed-vocabulary doc entry + quality-gate evidence)? [Completeness, evidence-gate-rule.md §Closed-vocabulary preset registry / Spec §FR-018]

## Operator Self-Service Re-Derivation

- [x] CHK066 Is the rule "an operator who reads a `run_summary` line on disk and applies the documented v1 table to each `evidence_gate_documents[i].signals` MUST get the recorded decision back exactly" stated as a hard guarantee? [Clarity, Spec §US3 AC#4 §SC-002 §SC-012 / evidence-gate-rule.md §Re-derivability guarantee]
- [x] CHK067 Is the rule "the answer is re-derivable from the operator-facing record alone, without re-running the binary and without reading source code" stated for US3 AC#4? [Clarity, Spec §US3 AC#4]
- [x] CHK068 Does the spec define the FR-016 evaluator-join key (`document_id` matches across `evidence_gate_documents` and `evaluation_run_summary.json`) so the cross-stage operator workflow is explicit? [Completeness, R-020.11 / Spec §FR-016]

## Verifiability of Policy Claims

- [x] CHK069 For every threshold (`8`, `0.70`, `0.25`, `>= 1`), is there a named unit test that verifies the boundary disposition (token-density exactly 8, confidence exactly 0.70, fraction exactly at boundary, count exactly 1)? [Measurability, Plan §Testing / module-invariants.md MI-6 / MI-7]
- [x] CHK070 For the 32 truth-table rows, is there a named parameterized unit test that covers every row? [Measurability, Plan §test_evidence_gate_decision_unit.py / module-invariants.md MI-7]
- [x] CHK071 For the two-metric quality gate, is there a named test that asserts the candidate-vs-legacy comparison on the FR-015 benchmark subset? [Measurability, Plan §test_quality_gate_two_metric_evidence_gate.py]
- [x] CHK072 Is the policy carrier (`contracts/evidence-gate-rule.md`) named as the operator-facing authoritative reference, not the source code? [Clarity, evidence-gate-rule.md §Re-derivability guarantee]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality**, not implementation correctness
