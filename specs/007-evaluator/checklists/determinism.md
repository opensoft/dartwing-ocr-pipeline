# Determinism & Reproducibility Requirements Checklist: Evaluator & Reporting

**Purpose**: Validate that determinism, byte-identical output, ordering, and reproducibility requirements in the spec are complete, unambiguous, measurable, and consistent. This is a "unit test for English" — it audits requirements quality, not implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Audience**: pre-PR reviewer (standard depth)

## Byte-Identical Output — Clarity & Measurability

- [ ] CHK001 Does the spec state explicitly that repeated evaluator runs on identical inputs MUST produce byte-identical output except for named exceptions? [Clarity, Spec §FR-018 / §SC-005]
- [ ] CHK002 Is the set of fields permitted to vary across runs exhaustively enumerated (`run_id`, "any explicitly-declared timestamp")? [Completeness, Spec §FR-018]
- [ ] CHK003 Is the byte-identical requirement stated both at the per-document and per-corpus level? [Consistency, Spec §US1 AC#8 / §US2 AC#7 / §FR-018]
- [ ] CHK004 Can "byte-identical" be objectively verified with a diff tool against the documented exception list? [Measurability, Spec §SC-005 / quickstart.md §5]
- [ ] CHK005 Does the Markdown run report (`evaluation_run_summary.md`) inherit the determinism obligation, or is it exempted? [Coverage, Spec §FR-021]

## `run_id` Semantics — Clarity

- [ ] CHK006 Is `run_id` generation required to be unique across invocations even within the same wall-clock second? [Clarity, Spec §Edge Cases (Run ID collision)]
- [ ] CHK007 Is `run_id` explicitly scoped to `evaluation_run_summary.json` only (not `evaluation_document.json`)? [Consistency, Spec §Key Entities / data-model.md §5]
- [ ] CHK008 Does the spec state that overwriting a prior `evaluation_run_summary.json` is permitted (file is generated, not canonical state)? [Clarity, Spec §Edge Cases]
- [ ] CHK009 Is `run_id`'s stability contract (changes every run, intentionally) distinguished from the determinism obligation (other fields must NOT change)? [Consistency, Spec §FR-018]

## JSON Serialization — Bounded Behavior

- [ ] CHK010 Does the spec require (or research.md pin) a consistent JSON serialization policy (indentation, key ordering, encoding, trailing newline)? [Clarity, research.md §10]
- [ ] CHK011 Is the floating-point rounding convention pinned so two Python minor-version environments produce the same bytes? [Measurability, research.md §10]
- [ ] CHK012 Is the key-ordering policy (`sort_keys=False` with explicit dataclass → dict order) stated rather than left to json.dumps defaults? [Clarity, research.md §10]
- [ ] CHK013 Does the spec or plan forbid ad-hoc reordering of output keys run-over-run? [Consistency, Spec §FR-018 / research.md §11]

## Ordering Requirements — Coverage

- [ ] CHK014 Is the ordering of `field_results` (Python dict order tied to `SCORED_FIELDS`) required, not just recommended? [Clarity, Spec §FR-004 / research.md §11]
- [ ] CHK015 Is `evaluation_run_summary.json:documents[]` required to be sorted by `document_id` ascending? [Completeness, Spec §FR-017]
- [ ] CHK016 Is `by_difficulty` key ordering (easy → medium → hard → missing_name) required to be deterministic? [Completeness, Spec §US2 AC#3]
- [ ] CHK017 Is the failing-documents list in the Markdown report required to be deterministically ordered (e.g., by `document_id`)? [Completeness, Spec §US5 AC#4]
- [ ] CHK018 Are tie-breakers defined for `by_field` emission order so its serialized representation is stable? [Gap, Spec §FR-015]

## Floating-Point Gate Threshold — Measurability

- [ ] CHK019 Is the 0.85 threshold comparison required to handle `0.849999...` cases explicitly? [Edge Case, Spec §Edge Cases]
- [ ] CHK020 Does the spec require the epsilon convention to be documented in code (even though the spec intentionally does not pin the value)? [Clarity, Spec §Edge Cases]
- [ ] CHK021 Is the epsilon applied asymmetrically (inclusive `>=` with tolerance bump), not as a two-sided tolerance that could also push 0.850001 below the gate? [Clarity, research.md §8]

## Corpus-Mode Reproducibility — Consistency

- [ ] CHK022 Does the spec state that lazy-eval-filled per-document `evaluation_document.json` files are byte-identical to files produced by direct per-document invocation? [Consistency, Spec §US2 AC#7 / quickstart.md §3]
- [ ] CHK023 Are there requirements to ensure corpus-mode and sequential per-document invocations yield an identical `evaluation_run_summary.json` (up to `run_id`)? [Completeness, Spec §FR-018]
- [ ] CHK024 Does the spec address rerun behavior when an existing `evaluation_document.json` is already valid (reuse vs regenerate)? [Gap, Spec §FR-022 / quickstart.md §3]

## Read-Only Inputs — Consistency

- [ ] CHK025 Is "inputs are read-only" stated without carve-outs (e.g., no implicit rewrite-on-schema-drift)? [Clarity, Spec §FR-019]
- [ ] CHK026 Is the read-only invariant stated to hold even on hard error paths (no partial writes on failure)? [Consistency, Spec §FR-019 / §FR-020]

## Independence From Upstream State — Coverage

- [ ] CHK027 Does the spec require evaluator output be independent of environment (time zone, locale, Python build, installed-but-unused packages)? [Coverage, Gap]
- [ ] CHK028 Is the "no network" constraint stated in a way that prevents implicit non-determinism (e.g., time-server lookups, telemetry)? [Coverage, Spec §FR-025]
- [ ] CHK029 Is "no model calls" redundantly pinned so evaluator determinism can never depend on stochastic inference? [Consistency, Spec §FR-025 / §Assumptions]

## Regression-Detection Workflow — Measurability

- [ ] CHK030 Does the spec or quickstart describe a concrete procedure by which two runs can be diffed, proving determinism? [Measurability, quickstart.md §5]
- [ ] CHK031 Is the determinism acceptance criterion (SC-005) quantified as "zero diff lines except the exempted fields", not just "the same"? [Clarity, Spec §SC-005]
- [ ] CHK032 Does the spec distinguish determinism (run-to-run on same inputs) from stability (release-to-release on same inputs)? [Gap, Spec §FR-018]

## Error Paths — Consistency with Determinism

- [ ] CHK033 Is "no partial output on hard error" stated consistently with determinism (a failed run leaves the filesystem in exactly one state: pre-invocation)? [Consistency, Spec §FR-020]
- [ ] CHK034 Does the spec require that hard-error messages themselves be deterministic (same file + same violation ⇒ same message), or explicitly exempt them? [Gap, Spec §FR-020]

## Notes

- Check items off as completed: `[x]`.
- A "no" on any CHK item is a spec (or plan/research) gap, not a coding problem.
- Use `[Gap]` items to prompt targeted spec amendments; use `[Measurability]` items to push vague statements toward quantifiable ones.
