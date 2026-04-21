# CLI & Error-Handling Requirements Checklist: Evaluator & Reporting

**Purpose**: Validate that CLI surface, subcommand behavior, exit-code semantics, lazy vs strict corpus mode, and hard-error handling requirements in the spec are complete, unambiguous, consistent, and measurable. This is a "unit test for English" — it audits requirements quality, not implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Audience**: pre-PR reviewer (standard depth)

## Subcommand Surface — Completeness

- [ ] CHK001 Does the spec pin the CLI invocation to `python -m ledgerlinc_ocr.evaluator` (not a bare script), matching the validator precedent? [Clarity, Spec §FR-022 / §Clarifications]
- [ ] CHK002 Are the two subcommand shapes (`evaluate document <folder>`, `evaluate corpus <root>`) stated verbatim so fixtures and quickstart cannot diverge? [Clarity, Spec §FR-022]
- [ ] CHK003 Does the spec forbid additional top-level subcommands not in {`evaluate document`, `evaluate corpus`} for this feature? [Gap, Spec §FR-022]
- [ ] CHK004 Is the positional-argument style (`<folder>` / `<root>`) documented rather than leaving flags vs positionals ambiguous? [Clarity, contracts/module-api.md §CLI contract]

## One-Document Mode — Behavior Specification

- [ ] CHK005 Does the spec require one-document mode to write `evaluation_document.json` into the supplied folder and nowhere else? [Clarity, Spec §FR-001]
- [ ] CHK006 Is the output side-effect scope ("writes nothing outside the target folder, does not modify the inputs") explicitly stated for one-document mode? [Completeness, Spec §US1 AC#7 / §FR-019]
- [ ] CHK007 Does the spec distinguish a low-scoring document (reported outcome, exit 0) from a hard error (exit non-zero)? [Clarity, Spec §US1 AC#7 / §FR-023]

## Corpus Mode — Behavior Specification

- [ ] CHK008 Does the spec require corpus mode to write `evaluation_run_summary.json` AND `evaluation_run_summary.md` at the corpus root? [Completeness, Spec §FR-014 / §FR-021]
- [ ] CHK009 Is the lazy-evaluation semantics (auto-run per-document eval for folders missing `evaluation_document.json`) stated as the default behavior post-clarification? [Clarity, Spec §Clarifications / §FR-022]
- [ ] CHK010 Is the strict mode (opt-out of lazy eval via `--no-lazy` or equivalent flag) stated as a first-class option? [Completeness, contracts/module-api.md §CLI contract]
- [ ] CHK011 Does the spec state corpus-mode output side-effect scope (writes only at corpus root + any missing per-document `evaluation_document.json`)? [Completeness, Spec §FR-022]
- [ ] CHK012 Is stdout streaming of the Markdown report required for corpus mode, and byte-identical to the on-disk `.md` file? [Clarity, Spec §FR-021]

## Exit-Code Semantics — Measurability

- [ ] CHK013 Does the spec (or module-api contract) enumerate exit codes explicitly (0 = clean, 2 = usage, 3 = hard error)? [Completeness, contracts/module-api.md §CLI contract]
- [ ] CHK014 Is the distinction between "document failed to pass gates" (exit 0) and "document could not be evaluated" (non-zero) stated? [Clarity, Spec §FR-023]
- [ ] CHK015 Does the spec require exit codes to be identical between one-document and corpus modes for the same error class? [Consistency, Spec §FR-022]
- [ ] CHK016 Is exit code 2 reserved for argparse/usage errors (wrong flags, missing positional) rather than ambiguously overloaded? [Clarity, contracts/module-api.md]

## Hard-Error Handling — Coverage

- [ ] CHK017 Does the spec enumerate the hard-error conditions exhaustively (missing input, unreadable input, schema-invalid input, `document_id` mismatch, `contract_set_version` drift, incomplete corpus without `--no-lazy` opt-in)? [Completeness, Spec §FR-013 / §FR-020 / §Edge Cases]
- [ ] CHK018 Is the "names the offending file" requirement for error messages stated for every hard-error path? [Clarity, Spec §Edge Cases / §SC-007]
- [ ] CHK019 Is "writes no partial artifact" stated consistently across one-document and corpus modes on hard error? [Consistency, Spec §FR-020]
- [ ] CHK020 Does the spec require human-readable (non-traceback) error messages, not raw Python exceptions leaked to stderr? [Gap / Clarity, Spec §SC-007]

## Lazy-Eval Error Semantics — Clarification Gap Audit

- [ ] CHK021 In lazy mode, does the spec state that a single per-document hard error aborts the whole corpus run? [Clarity, Spec §FR-020 / §FR-022]
- [ ] CHK022 Is the filesystem state after a corpus-mode hard error defined (successful per-document files stay; summary not written)? [Coverage, research.md §13]
- [ ] CHK023 Does the spec state whether lazy-mode aborts with a single error message or accumulates all errors before aborting? [Gap, Spec §FR-020]

## Partial-Corpus Opt-In — Coverage

- [ ] CHK024 Does the spec cover the N<20 partial corpus case and what opt-in looks like? [Coverage, Spec §Edge Cases (Partial corpus evaluation)]
- [ ] CHK025 Is "without opt-in, any corpus with missing per-document results is a bug" stated consistently post-clarification? [Consistency, Spec §US2 AC#8 / §Clarifications]
- [ ] CHK026 Is the `--no-lazy` flag's interaction with partial-corpus opt-in documented (they are distinct concerns)? [Gap, contracts/module-api.md]

## Output-Format Flags — Consistency

- [ ] CHK027 Does the spec permit (and the module-api contract define) a `--json` vs `--text` switch on both subcommands? [Clarity, contracts/module-api.md §CLI contract]
- [ ] CHK028 Is the default output style (`--text`) stated as the one a developer gets without flags? [Completeness, contracts/module-api.md]
- [ ] CHK029 Is the Markdown stdout stream (corpus mode) required regardless of `--json` vs `--text`, or is it gated by `--text`? [Gap, Spec §FR-021 / contracts/module-api.md]

## Module API vs CLI Parity — Consistency

- [ ] CHK030 Does every CLI outcome have a typed Python API equivalent (`DocumentEvaluationOutcome`, `RunSummaryOutcome`)? [Consistency, contracts/module-api.md §Public functions]
- [ ] CHK031 Is the contract that "the module API never shells out to the CLI" stated so corpus-mode lazy eval is in-process? [Clarity, research.md §13]
- [ ] CHK032 Are the Python exceptions (`ContractSetVersionMismatchError`, `DocumentIdMismatchError`, `SchemaValidationError`, `EmptyCorpusError`) stated as the module-level error surface? [Completeness, contracts/module-api.md §Public exceptions]

## Harness/Pipeline Boundary — Consistency

- [ ] CHK033 Does the spec forbid CLI paths from invoking extraction, models, or network? [Clarity, Spec §FR-025]
- [ ] CHK034 Is "evaluator does not import from `ledgerlinc_ocr.pipeline` or `.preprocessing`" stated as a boundary invariant? [Traceability / Consistency, contracts/module-api.md §Stability guarantees / Constitution §I]
- [ ] CHK035 Does the spec restrict CLI filesystem reach to the supplied folder/root (no writes elsewhere under any flag)? [Completeness, Spec §FR-025 / §US1 AC#7]

## Human-Readable Report Behavior — Clarity

- [ ] CHK036 Is the report's structure (headline metrics, by-difficulty table, failing-document list) defined precisely enough that two implementations produce identical Markdown? [Clarity, Spec §FR-021 / research.md §14]
- [ ] CHK037 Is the zero-failing-documents case handled by the report specification, not left implicit? [Coverage, Spec §US5 AC#3]
- [ ] CHK038 Is the failing-document entry shape (document_id + difficulty + one-line reason) pinned? [Completeness, Spec §US5 AC#2]

## Notes

- Check items off as completed: `[x]`.
- A "no" on any item is a spec (or module-api contract) gap, not an implementation defect.
- `[Gap]` items surface missing requirement definitions; `[Consistency]` items ensure multiple sections agree; `[Measurability]` items push vague prose toward testable criteria.
