# Scope Quality Checklist: GPU MVP Promotion

**Purpose**: Validate that scope boundaries — what this feature IS and what it explicitly IS NOT — are written with the clarity, completeness, and enforceability needed to keep a validation/promotion slice from drifting into product behavior.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements that describe scope*, not the implementation. Every item evaluates whether the spec's scope writing is unambiguous, complete, and testable.

## In-Scope Definition

- [X] CHK001 Is the in-scope surface stated with precise verbs (validate / promote / record / document) and never with implementation verbs (build / refactor / add)? [Clarity, Spec §Scope discipline]
- [X] CHK002 Are the six in-scope work threads — readiness gate, deferred GPU verification, benchmark, quality gate, runbook, promotion decision — each mapped to at least one user story and one FR family? [Completeness, Spec §User Scenarios, §Functional Requirements]
- [X] CHK003 Is "validation, promotion, documentation slice" defined in operator-testable terms (what changes on disk after this feature lands)? [Clarity, Spec §Scope discipline]
- [X] CHK004 Is the FR-028 explicit-off legacy path identified as the *only* new product behavior permitted by this feature, and only conditionally (promotion path is chosen)? [Clarity, Spec §FR-032]
- [X] CHK005 Are the deliverable artifacts of this feature enumerated (Appendix A entries, Appendix B entries, runbook update, promotion decision record) with their authoritative file paths? [Completeness, Spec §FR-023, §FR-024, §FR-025, §FR-026]

## Out-of-Scope Enumeration

- [X] CHK006 Are all seven PRD §"Explicitly out of scope" items reproduced in the spec's §Out of Scope block without omission? [Completeness, Spec §Out of Scope]
- [X] CHK007 Is each Out-of-Scope item phrased as a testable prohibition (an inspector can confirm the spec violates it or not)? [Measurability, Spec §Out of Scope]
- [X] CHK008 Is "Removing CPU/stub paths" explicitly distinguished from "Operating demo is GPU-only" — i.e., is the runbook-vs-CI boundary unambiguous? [Clarity, Spec §Out of Scope, §FR-030]
- [X] CHK009 Is the prohibition on new persisted artifacts (FR-032) stated in terms a reviewer can apply to a diff (no new file under `tests/`, no new JSON output, no new top-level `run_summary` field)? [Measurability, Spec §FR-032]
- [X] CHK010 Is the prohibition on new `run_summary` fields beyond feature 020's set (FR-032) cross-linked to feature 020's actual emitted field list, so a reviewer can count? [Traceability, Spec §FR-032]
- [X] CHK011 Is the Jetson `edge-fast` exclusion stated with enough specificity that a reviewer encountering a partial Jetson reference can recognize it as out-of-scope drift? [Clarity, Spec §Out of Scope]
- [X] CHK012 Is the prohibition on remote cloud execution / credentials stated with the boundary case (workstation GPU is allowed; cloud-managed GPU is not)? [Clarity, Spec §Out of Scope]
- [X] CHK013 Is the prohibition on over-time surveillance for `evidence_gate_suppressed_fallback_count` explicit about the deferral target ("a later ops feature")? [Traceability, Spec §Out of Scope]

## Cross-Feature Boundary Discipline

- [X] CHK014 Does the spec name every feature this slice consumes (014–019 GPU lineage, 020 evidence gate, 007 evaluator, 005 voter config) and distinguish "consumes" from "modifies"? [Completeness, Spec §Assumptions]
- [X] CHK015 Is the consumption of feature 020's `RunSummary.SCHEMA_VERSION = 0.1.7` bounded to read-only (no new fields, no schema bump in this feature)? [Clarity, Spec §FR-032]
- [X] CHK016 Is the consumption of feature 020's deterministic suppression predicate bounded to read-only (no modification of the predicate, only exercise of its GPU lane)? [Clarity, Spec §Assumptions]
- [X] CHK017 Is the consumption of feature 007's evaluator surface bounded to read-only (no new metric, no new evaluator flag, no schema change to `evaluation_*.json`)? [Clarity, Spec §Assumptions, §FR-019]
- [X] CHK018 Is the consumption of feature 005's voter config bounded to read-only (no new config key, no schema change)? [Clarity, Spec §FR-002]
- [X] CHK019 Are the appendices in feature 020's `quickstart.md` (Appendix A, Appendix B) named with stable references so cross-feature edits don't break traceability? [Traceability, Spec §FR-023, §FR-024]

## Schema & Artifact Preservation (FR-031)

- [X] CHK020 Is FR-031 stated as a complete schema-preservation contract (no canonical artifact schema change, no filename change, no folder-contract change)? [Completeness, Spec §FR-031]
- [X] CHK021 Are the four canonical artifact filenames (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) implicitly protected by FR-031, or is the protection enumerated? [Completeness, Spec §FR-031]
- [X] CHK022 Is the per-document folder contract (`tests/stage1_vendor_identity/inv_XXX_<difficulty>/...`) named in the FR-031 preservation set? [Completeness, Spec §FR-031]
- [X] CHK023 Does the spec's preservation language cover both *structural* schema (keys/types) and *semantic* schema (allowed values, enum sets)? [Clarity, Gap]

## New-Behavior Prohibition (FR-032)

- [X] CHK024 Is FR-032 enumerated explicitly — every single category of new product behavior is named (no persisted artifact, no new run_summary field, no remote cloud, no Jetson, no over-time surveillance)? [Completeness, Spec §FR-032]
- [X] CHK025 Is the FR-028 explicit-off legacy path the *only* carve-out, and is it gated on the promotion-to-default decision being chosen? [Clarity, Spec §FR-028, §FR-032]
- [X] CHK026 Is "new product behavior" defined precisely enough that a reviewer can distinguish a runbook update (allowed) from a code module (forbidden)? [Clarity, Spec §FR-032]
- [X] CHK027 Is the shell-helper carve-out (Ollama check helper outside the package) clearly described as "outside `dartwing_ocr`", so a reviewer recognizes the FR-032 line? [Clarity, Spec §FR-002]

## Corpus Mutability (FR-033)

- [X] CHK028 Is FR-033 specific about which corpus is protected (`tests/stage1_vendor_identity/` per-document folders) and which mutation source is forbidden (GPU output regenerating baselines)? [Clarity, Spec §FR-033]
- [X] CHK029 Is the "separate contract decision approves it" exception clear about who/how (a future feature, an explicit /speckit.specify, etc.)? [Clarity, Spec §FR-033]
- [X] CHK030 Is the scratch-copy rule (FR-018) consistent with FR-033's no-baseline-regeneration rule (FR-033 closes the door; FR-018 redirects writes)? [Consistency, Spec §FR-018, §FR-033]

## Scope-Slippage Risks

- [X] CHK031 Are requirements present that prevent an enthusiastic implementor from adding a "small" Ollama health-check module inside `dartwing_ocr` (FR-002 carve-out boundary)? [Coverage, Spec §FR-002, §FR-032]
- [X] CHK032 Are requirements present that prevent runbook updates from cascading into pipeline-code changes (runbook is the only delivery surface for FR-025)? [Coverage, Spec §FR-025, §FR-032]
- [X] CHK033 Are requirements present that prevent the promotion-to-default path from quietly adding telemetry, dashboards, or alerting beyond what feature 020 already emits? [Coverage, Spec §FR-032, Out of Scope]
- [X] CHK034 Are requirements present that prevent the FR-028 explicit-off legacy path from becoming a new operational mode (versus a single inverted flag/env var on the existing surface)? [Coverage, Spec §FR-028]

## Scope Boundary Testability

- [X] CHK035 Can each Out-of-Scope item be falsified by inspecting a single artifact (diff, run_summary, runbook commit) — i.e., is each prohibition operationally observable? [Measurability, Spec §Out of Scope]
- [X] CHK036 Is the boundary between "validation evidence" (in scope) and "validation infrastructure" (mostly out of scope, except runbook + appendices) explicit? [Clarity, Gap]
- [X] CHK037 Does the spec define what happens when implementation work surfaces an apparent need that crosses an Out-of-Scope line (defer to a future feature, not absorb)? [Coverage, Gap]

## Notes

- This checklist is a quality gate for *scope writing*, not a checklist of scope items themselves.
- The principal scope-risk for this feature is silent scope creep via the runbook, the Ollama helper, or the promotion-to-default path expanding into telemetry/UX. Items CHK031–CHK034 target that risk explicitly.
- A scope-quality issue here typically manifests downstream as a forbidden code change in plan/tasks; catching the writing-level ambiguity first is the cheap win.
