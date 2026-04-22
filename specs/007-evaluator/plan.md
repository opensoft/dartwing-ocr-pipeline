# Implementation Plan: Evaluator & Reporting (Stage 1 Vendor-Identity)

**Branch**: `007-evaluator` | **Date**: 2026-04-20 | **Spec**: `specs/007-evaluator/spec.md`
**Input**: Feature specification from `/specs/007-evaluator/spec.md`

## Summary

Build a new `ledgerlinc_ocr.evaluator` subpackage that compares a document's hand-labeled `expected.json` against the pipeline's `final_structured_payload.json` per the normalization rules, partial-match policy, weights, and pass gates in `docs/stage1-vendor-identity/scoring.md`, and writes a schema-valid `evaluation_document.json` into the same folder. A corpus mode iterates every per-document folder under a corpus root, lazily evaluates any folder missing `evaluation_document.json` (only hard-failing when pipeline inputs themselves are missing or invalid), and writes `evaluation_run_summary.json` plus a canonical Markdown `evaluation_run_summary.md` at the corpus root (also streamed to stdout).

Technical approach: a pure-Python, offline, deterministic library + argparse CLI that mirrors the existing `ledgerlinc_ocr.validator` module layout. No PyTorch, no network, no model calls. Normalization, comparison, gate evaluation, and aggregation are implemented as small, independently testable modules whose contracts flow through typed dataclasses. All JSON output is serialized through a single writer that enforces `sort_keys=False`, explicit key ordering, and a trailing newline for byte-level determinism. Schema validation is reused from the existing `jsonschema` Draft 2020-12 stack already wired up for the validator. The evaluator is invoked via `python -m ledgerlinc_ocr.evaluator evaluate document <folder>` and `python -m ledgerlinc_ocr.evaluator evaluate corpus <root>` (per clarification Q5).

## Technical Context

**Language/Version**: Python 3.12 (matches devcontainer base and existing `pyproject.toml`).
**Primary Dependencies**: `jsonschema>=4.22,<5` (Draft 2020-12, already declared), `pydantic>=2.7,<3` (already declared; typed result models to match the validator style). Python stdlib only for everything else: `argparse`, `json`, `pathlib`, `dataclasses`, `re`, `hashlib`, `datetime`, `uuid`.
**Storage**: Filesystem only. Reads `expected.json` and `final_structured_payload.json` inside per-document folders under `tests/stage1_vendor_identity/inv_XXX_<difficulty>/` (or a user-supplied corpus root). Writes `evaluation_document.json` into the same folder and `evaluation_run_summary.json` + `evaluation_run_summary.md` at the corpus root.
**Testing**: `pytest>=8.2,<9` (already declared dev extra). New tests live under `tests/evaluator_tests/` and a schema-level contract test under `tests/contract_tests/`. `pytest-socket` continues to block network access in tests.
**Target Platform**: Linux (devcontainer Python 3.12). CPU-only. Fully offline — no Ollama, no PaddleOCR, no network. Runs from host and devcontainer identically.
**Project Type**: Single-project Python library + CLI, co-located with the existing `validator`, `preprocessing`, and `pipeline` subpackages under `src/ledgerlinc_ocr/`.
**Performance Goals**: One-document evaluation ≤ 1 s wall-clock on a developer workstation (SC-001); 20-document corpus evaluation ≤ 5 s (SC-002). Both easily met — everything is string comparison and arithmetic over ≤ 18 scored fields per document.
**Constraints**:
- Deterministic byte-identical output run-over-run except for `run_id` (FR-018).
- No network access at runtime or in tests (`pytest-socket`).
- No invocation of extraction pipeline, model, or external process (FR-025).
- Must not modify inputs (FR-019).
- Must produce no partial output on hard error (FR-020).
- Contract-set pinned to `1.1.0` (MINOR-forward compat per FR-013 — same major, artifact minor ≤ pinned minor); any non-compatible drift hard-fails.

**Scale/Scope**: 20-document stage-1 corpus; 18 scored fields per document; 5 difficulty/bucket keys (`easy`, `medium`, `hard`, `missing_name`); one run per invocation. Code footprint target: < 1 kLOC across `src/ledgerlinc_ocr/evaluator/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution: `.specify/memory/constitution.md` (v1.0.0, ratified 2026-04-12).

| Principle | Assessment |
|---|---|
| **I. One Repo, Clear Runtime Boundaries** | **PASS**. Evaluator sits squarely in the harness layer (`evaluation and reporting` per §I). It never invokes the extraction pipeline, consensus, or routing; it reads the committed artifacts those stages produce and writes evaluation artifacts. No runtime boundaries are collapsed. |
| **II. Evidence-First, Schema-First Design** | **PASS**. Every input the evaluator reads (`expected.json`, `final_structured_payload.json`) is schema-validated before comparison (FR-013). Every output it writes (`evaluation_document.json`, `evaluation_run_summary.json`) is schema-validated before being persisted. The pinned `contract_set_version` (default `"1.1.0"`, MINOR-forward-compat per FR-013) is enforced at both ingress and egress. |
| **III. Deterministic Control Over Model Output** | **PASS**. The evaluator contains zero model calls. Normalization, comparison, weighting, gate evaluation, aggregation, and routing assessment are 100% deterministic code. Confidence from `final_structured_payload.json` is deliberately ignored for scoring (per `scoring.md` "Confidence Tracking"). |
| **IV. Provenance and Review Safety** | **PASS**. FR-012 enforces all four missing-name invariants as a hard gate on `review_routing_passed`. A "correct value" prediction cannot pass if `present`/`inferred` are wrong (US4 AC#2). The evaluator treats `present`/`inferred`/`manual_review_required`/`review_reason` as hard-comparison fields (FR-006: never `partial_match`). |
| **V. Benchmarkable and Reproducible Delivery** | **PASS**. Supports one-document and corpus modes (FR-022). Deterministic outputs (FR-018, SC-005) enable regression detection. The canonical Markdown report (FR-021) and `evaluation_run_summary.json` together answer "is the pipeline better than yesterday?" from one place. |

**Stage 1 scope constraints**: respected. No line items, no cloud path, no ensemble logic, no latency gate as release criterion.

**Quality gates** (constitution §Quality Gates):
- Gate 1 (boundary separation): evaluator lives entirely on the harness side. Evaluator code never imports from `pipeline/` or `preprocessing/`.
- Gate 2 (schema updates): this feature only **consumes** the frozen evaluation schemas; it does not amend them. If implementation discovers a schema gap, the fix goes through `contracts/stage1_vendor_identity/AMENDMENTS.md`, not through a silent schema edit.
- Gate 4 (verifiable local execution): covered by the quickstart + `tests/evaluator_tests/`.
- Gate 6 (preserve comparison against labeled truth): this is literally the feature.

**Result**: Constitution Check **PASSES** pre-design. Complexity Tracking is empty. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/007-evaluator/
├── plan.md              # This file
├── spec.md              # Clarified feature specification
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/           # Phase 1 output (this command)
│   └── module-api.md    # Python public API stability surface for ledgerlinc_ocr.evaluator
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

New code lives exclusively under `src/ledgerlinc_ocr/evaluator/` and `tests/evaluator_tests/`. No existing file is modified except `pyproject.toml` (to register the optional script entry point) and `.claude/CLAUDE.md` contexts. The layout mirrors the established `validator/` subpackage for consistency with the team's existing conventions.

```text
src/ledgerlinc_ocr/evaluator/
├── __init__.py              # Public surface: evaluate_document, evaluate_corpus, result dataclasses, exceptions
├── __main__.py              # Thin re-export of cli.main for `python -m ledgerlinc_ocr.evaluator`
├── cli.py                   # argparse: `evaluate document <folder>` / `evaluate corpus <root>`
├── document.py              # Per-document orchestration: read → validate → compare → gate → write
├── corpus.py                # Corpus aggregator + lazy per-document evaluation + report dispatch
├── normalize.py             # Normalization rules per scoring.md (company, street, state, postal, website, phone, email, tax_id)
├── compare.py               # Field comparators → {match, partial_match, mismatch, missing_prediction, unexpected_prediction, not_applicable}
├── gates.py                 # vendor_identity_passed, review_routing_passed, overall_passed (incl. missing-name invariants)
├── scoring.py               # Weights, document_score, field_accuracy (partial_count derivation)
├── report.py                # Deterministic Markdown renderer for evaluation_run_summary.md (+ stdout)
├── io.py                    # Deterministic JSON reader/writer + write_text (sort_keys=False, explicit key order, UTF-8, trailing newline)
├── schema.py                # Thin wrapper that loads evaluation_document.schema.json + evaluation_run_summary.schema.json via the existing validator.loader
├── exceptions.py            # EvaluatorError base + ContractSetVersionMismatchError / DocumentIdMismatchError / SchemaValidationError / EmptyCorpusError
└── outcomes.py              # Pydantic outcome models: DocumentEvaluationOutcome, RunSummaryOutcome

tests/evaluator_tests/
├── __init__.py
├── fixtures/                # Committed per-document fixture pairs (expected.json + final_structured_payload.json) covering every scoring.md rule
│   ├── all_match/
│   ├── normalization_cases/
│   ├── partial_match_cases/
│   ├── missing_name_valid/
│   ├── missing_name_violations/   # one subfolder per invariant violation
│   ├── secondary_identifier_gates/
│   └── corpus_20/          # full 20-doc mini corpus for run-summary tests
├── test_normalize.py
├── test_compare.py
├── test_gates.py
├── test_scoring.py
├── test_document_evaluator.py
├── test_corpus_aggregator.py
├── test_report.py
├── test_determinism.py
└── test_cli.py

tests/contract_tests/
└── test_evaluation_artifacts.py   # Validates evaluator outputs against the frozen schemas
```

**Structure Decision**: Single-project Python library + CLI. The new `src/ledgerlinc_ocr/evaluator/` subpackage mirrors the existing `validator/` subpackage surface (module layout, `__main__.py` convention, argparse grouping, typed public API in `__init__.py`). This keeps the harness codebase navigable for anyone who has used the validator and keeps review diffs small by reusing `jsonschema` loading, the contracts directory, and the `pytest` + `pytest-socket` configuration already in place.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|

*(None. Constitution Check passes without exceptions.)*
