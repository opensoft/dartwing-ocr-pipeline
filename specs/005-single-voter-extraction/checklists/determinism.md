# Determinism & Reconciliation Checklist: Single-Voter Edge Extraction (Stage 1)

**Purpose**: PR-review aid for validating that the spec specifies — unambiguously and without
gaps — which parts of the extractor are deterministic code versus model-proposed, how the
reconciliation pipeline behaves under fixed inputs, and how SC-009's determinism claim is scoped.
Every item tests the requirements themselves — not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: PR-review aid
**Audience**: Spec author + reviewer (pre-`/speckit.tasks`)

## Code-vs-Model Boundary (Constitution III)

- [x] CHK001 Does the spec explicitly state that evidence reconciliation is code, not model judgment? [Clarity, Spec §US2 §FR-010]
- [x] CHK002 Does the spec explicitly state that `status` derivation is code, not model-reported? [Clarity, Spec §FR-014]
- [x] CHK003 Does the spec explicitly state that `company_name.present` / `company_name.inferred` are set by code, overriding model claims when evidence is empty? [Clarity, Spec §FR-012 §US3 AC#3]
- [x] CHK004 Does the spec explicitly state that null-on-missing defaults are applied by code, not by the model? [Clarity, Spec §FR-016 §US5 AC#3]
- [x] CHK005 Does the spec explicitly state that the ungrounded-confidence cap is applied by code, after reconciliation? [Clarity, Spec §FR-011 §Clarifications Q1]
- [x] CHK006 Does the spec distinguish "confidence is a signal" from "confidence is provenance"? [Clarity, Spec §FR-011 §Constitution III]

## Ungrounded-Confidence Cap (FR-011 / Clarifications Q1)

- [x] CHK007 Is the cap rule stated as a hard ceiling (`confidence = min(confidence, CAP)`) rather than a multiplicative factor or zero-out? [Clarity, Spec §Clarifications Q1 §FR-011]
- [x] CHK008 Is the trigger condition stated unambiguously (post-reconciliation `evidence == []`)? [Clarity, Spec §FR-011]
- [x] CHK009 Is the cap application scope stated (every `value_confidence_evidence` field, `total_amount.confidence`, `document_type.confidence`)? [Completeness, Spec §FR-011]
- [x] CHK010 Is the model's `value` explicitly preserved under the cap rule (only `confidence` is clipped)? [Clarity, Spec §FR-011 §US2 AC#3]
- [x] CHK011 Is the concrete numeric value of `CAP` either pinned in the spec or explicitly deferred to the plan phase, without leaving the requirement ambiguous? [Completeness, Spec §FR-011 §Clarifications Q1]

## Evidence-Reconciliation Pipeline (US2)

- [x] CHK012 Is the evidence-format filter (regex `^p\d+_[bl]\d+$`) named as a step distinct from the evidence-resolution filter (must exist in packet)? [Clarity, Spec §FR-010 §US2 AC#1]
- [x] CHK013 Is the warnings-emission requirement stated for every dropped ID (naming the field and the dropped ID)? [Completeness, Spec §FR-010 §US2 AC#2]
- [x] CHK014 Is the deduplication / ordering rule for surviving evidence IDs specified (or explicitly deferred)? [Gap, Spec §US2]
- [x] CHK015 Is the behavior of the cross-document bogus-ID case specified (ID that looks valid but belongs to a different document)? [Coverage, Spec §Edge Cases]

## Provenance Override Semantics (FR-012 / FR-013 / US3)

- [x] CHK016 Is the override trigger specified precisely (`company_name.evidence == []` after reconciliation, regardless of model claim)? [Clarity, Spec §FR-012 §US3 AC#3]
- [x] CHK017 Is the positive-path semantics (`company_name.evidence != []`) stated alongside the override path (`present=true, inferred=false` when grounded)? [Completeness, Spec §US3 AC#1]
- [x] CHK018 Is the exclusive-or invariant (`present XOR inferred`) stated as a hard programmer-check, not just a schema hint? [Clarity, Spec §FR-013 §US3 AC#5]
- [x] CHK019 Is the override discoverability requirement stated (`extraction_notes` or `warnings` entry records the override)? [Completeness, Spec §US3 AC#3]
- [x] CHK020 Is the non-regression obligation on the 5 missing-name corpus documents stated as a measurable success criterion (100%)? [Measurability, Spec §SC-002]

## Null-on-Missing Defaulting (FR-016)

- [x] CHK021 Is the trigger condition stated (model response is valid JSON but lacks a required sub-field)? [Clarity, Spec §FR-016 §US5 AC#3]
- [x] CHK022 Is the exact default shape specified per field type (scalar vs `total_amount`)? [Completeness, Spec §FR-016]
- [x] CHK023 Is the obligation to name the defaulted field in `warnings` stated? [Completeness, Spec §FR-016]
- [x] CHK024 Is the obligation to set `status = "partial"` on defaulting stated? [Clarity, Spec §FR-016 §FR-014]

## Status Derivation (FR-014)

- [x] CHK025 Is the `status = "success"` condition specified precisely (meaningful artifact, no non-fatal warnings)? [Clarity, Spec §FR-014 §US1 AC#5]
- [x] CHK026 Is the `status = "partial"` condition specified precisely (at least one: JSON repair, evidence drop, sub-field default)? [Clarity, Spec §FR-014]
- [x] CHK027 Is the `status = "failure"` condition specified precisely (no meaningful result; defaulted artifact written)? [Clarity, Spec §FR-014 §US5 AC#4]
- [x] CHK028 Is status derivation required to be deterministic given a fixed model response? [Clarity, Spec §FR-014 §SC-009]
- [x] CHK029 Is the consistency rule between `status` and `warnings` stated (success → no hard-failure warning; partial → at least one non-fatal warning; failure → explanatory warning)? [Consistency, Spec §US1 AC#5]
- [x] CHK030 Does the spec pin the precedence of the status conditions (which wins when multiple apply)? [Ambiguity, Spec §FR-014]

## Determinism Scope (SC-009 / Assumptions)

- [x] CHK031 Is "schema-shape determinism" named as contractual? [Clarity, Spec §SC-009]
- [x] CHK032 Is "reconciliation determinism given fixed model response" named as contractual? [Clarity, Spec §SC-009]
- [x] CHK033 Is "status-derivation determinism" named as contractual? [Clarity, Spec §SC-009]
- [x] CHK034 Is "provenance-invariant determinism" named as contractual? [Clarity, Spec §SC-009]
- [x] CHK035 Is "bit-exact model value strings" explicitly NOT named as contractual (avoiding an impossible promise)? [Clarity, Spec §Assumptions §SC-009]
- [x] CHK036 Are the allowed-to-vary elements (`processed_at`, `pipeline_version`) named? [Completeness, Spec §SC-009]

## Ordering / Sort Stability

- [x] CHK037 Does the spec address whether `warnings` is required to be in a deterministic order (sorted, first-seen, or unspecified)? [Gap, Spec §US5 AC#5]
- [x] CHK038 Does the spec address whether `extraction_notes` is required to be in a deterministic order? [Gap, Spec §US2 AC#5]
- [x] CHK039 Does the spec address whether deduplication is required inside `warnings` / `extraction_notes`? [Gap]

## Model Sampling (Clarifications Q5)

- [x] CHK040 Does the spec state the default sampling posture (temperature=0, fixed seed where supported) as a per-voter-config default rather than a hardcoded extractor rule? [Clarity, Spec §Clarifications Q5 §Assumptions]
- [x] CHK041 Does the spec explicitly acknowledge that temp=0 + seed is best-effort, not bit-exact? [Clarity, Spec §Assumptions]

## Document-Type Coercion

- [x] CHK042 Is the forced coercion `document_type.value = "invoice"` specified as deterministic (code, not model choice)? [Clarity, Spec §FR-009 §Edge Cases]
- [x] CHK043 Is the confidence-lowering behavior on "not an invoice" model judgment specified, with the `extraction_notes` reporting obligation? [Completeness, Spec §FR-009 §Edge Cases]

## Reconciliation Non-Regression

- [x] CHK044 Does the spec state that the reconciliation function's output is a pure function of `(preprocess_packet, model_response, voter_config)`? [Clarity, Spec §Key Entities "Reconciliation step"]
- [x] CHK045 Does the spec state that re-running reconciliation over a recorded model response produces the same artifact (modulo `processed_at` / `pipeline_version`)? [Measurability, Spec §SC-009]
