# Python Module API: `ledgerlinc_ocr.evaluator`

**Feature**: 007-evaluator
**Contract-set version this API consumes**: `1.0.0`
**Stability**: public — names below are part of the stage 1 harness surface. Changes require an entry in `contracts/stage1_vendor_identity/AMENDMENTS.md` or a superseding feature.

This file is the authoritative list of the evaluator's public Python API. The module layout is internal and may change without notice, but every name in this document MUST remain importable from `ledgerlinc_ocr.evaluator` with the signature and return shape shown.

---

## Public functions

### `evaluate_document`

```python
def evaluate_document(
    folder: str | Path,
    *,
    contract_set_version: str | None = None,
) -> DocumentEvaluationOutcome: ...
```

**Purpose**: Evaluate one per-document folder. Reads `expected.json` and `final_structured_payload.json` from the folder, compares them, writes `evaluation_document.json` into the same folder, and returns a typed outcome.

**Parameters**:
- `folder`: path to a per-document folder.
- `contract_set_version`: optional pin; defaults to the version declared in the inputs. MUST match `"1.0.0"` for stage 1.

**Returns**: `DocumentEvaluationOutcome` (see data-model.md §11).

**Raises**:
- `FileNotFoundError` — `expected.json` or `final_structured_payload.json` missing.
- `ContractSetVersionMismatchError` — either input reports a `contract_set_version` other than `"1.0.0"`, or they disagree.
- `DocumentIdMismatchError` — inputs disagree on `document_id`.
- `SchemaValidationError` — either input fails its frozen schema.

The function MUST NOT write any output on a raised exception (FR-020).

**Side effects**: writes `evaluation_document.json` into `folder` on clean completion. Does not modify inputs (FR-019).

---

### `evaluate_corpus`

```python
def evaluate_corpus(
    root: str | Path,
    *,
    contract_set_version: str | None = None,
    lazy: bool = True,
) -> RunSummaryOutcome: ...
```

**Purpose**: Evaluate every per-document folder under `root`. When `lazy=True` (default), any folder missing `evaluation_document.json` is transparently evaluated via `evaluate_document`. Writes `evaluation_run_summary.json` and `evaluation_run_summary.md` at `root`, and prints the Markdown to stdout.

**Parameters**:
- `root`: path to the corpus root (a directory of per-document folders).
- `contract_set_version`: optional pin (see above).
- `lazy`: if `False`, the function hard-fails when any folder lacks `evaluation_document.json`; if `True`, it calls `evaluate_document` on those folders before aggregating.

**Returns**: `RunSummaryOutcome` (see data-model.md §11).

**Raises**: same as `evaluate_document` for any single document's inputs, plus:
- `EmptyCorpusError` — no per-document folders found under `root`.

**Determinism**: byte-identical outputs across invocations on the same inputs except for `run_id` and any optional timestamp-like fields (FR-018).

---

## Public dataclasses and enums

Re-exported from `ledgerlinc_ocr.evaluator`:

- `ResultLabel` (enum: `match`, `partial_match`, `mismatch`, `missing_prediction`, `unexpected_prediction`, `not_applicable`)
- `FieldResult`
- `ComparisonSummary`
- `DocumentPassFail`
- `DocumentEvaluation`
- `DifficultyStats`
- `OverallMetrics`
- `ConsensusMetrics`
- `DocumentListEntry`
- `RunSummary`
- `DocumentEvaluationOutcome` (Pydantic)
- `RunSummaryOutcome` (Pydantic)

See `specs/007-evaluator/data-model.md` for full field definitions and invariants.

---

## Public exceptions

All exceptions subclass a single base for easy catch:

```python
class EvaluatorError(Exception): ...
class ContractSetVersionMismatchError(EvaluatorError): ...
class DocumentIdMismatchError(EvaluatorError): ...
class SchemaValidationError(EvaluatorError): ...
class EmptyCorpusError(EvaluatorError): ...
```

`FileNotFoundError` is not subclassed — the stdlib exception is re-raised as-is so callers can catch it with their existing patterns.

---

## CLI contract

Entry point: `python -m ledgerlinc_ocr.evaluator` (per clarification Q5).

### `evaluate document`

```
python -m ledgerlinc_ocr.evaluator evaluate document <folder> \
    [--contract-set-version 1.0.0] \
    [--json | --text]
```

- Writes `evaluation_document.json` into `<folder>`.
- Prints a short human-readable summary to stdout by default (`--text`), or the outcome as JSON with `--json`.
- Exit codes:
  - `0` — clean completion (document may still be a fail; that is reported in the outcome, not via exit code; FR-023).
  - `2` — usage error (bad arguments, missing folder, CLI parse failure).
  - `3` — hard evaluation error (missing/invalid inputs, schema drift, `document_id` mismatch).

### `evaluate corpus`

```
python -m ledgerlinc_ocr.evaluator evaluate corpus <root> \
    [--contract-set-version 1.0.0] \
    [--no-lazy]
```

- Writes `evaluation_run_summary.json` and `evaluation_run_summary.md` at `<root>`.
- Prints the Markdown report to stdout (always; byte-identical to the `.md` file per FR-021). Corpus mode does NOT accept `--json`/`--text`: stdout is always Markdown; the machine-readable `evaluation_run_summary.json` is already written to disk at a known path (`<root>/evaluation_run_summary.json`) and is the machine-consumable surface.
- With `--no-lazy`, folders lacking (or with an unreadable/schema-invalid) `evaluation_document.json` cause exit code `3`.
- Exit codes same as `evaluate document` (`0`, `2`, `3`).

### Examples (normative)

```bash
# One document, default output:
$ python -m ledgerlinc_ocr.evaluator evaluate document tests/stage1_vendor_identity/inv_001_easy

# One document, machine-readable outcome:
$ python -m ledgerlinc_ocr.evaluator evaluate document inv_001_easy --json

# Full corpus, lazy evaluation of any missing per-document results:
$ python -m ledgerlinc_ocr.evaluator evaluate corpus tests/stage1_vendor_identity

# Full corpus, strict (every folder must already have evaluation_document.json):
$ python -m ledgerlinc_ocr.evaluator evaluate corpus tests/stage1_vendor_identity --no-lazy
```

---

## Stability guarantees

The following MUST hold across any change within the 007-evaluator feature:
- The names in "Public functions" and "Public dataclasses and enums" remain importable from `ledgerlinc_ocr.evaluator`.
- The CLI subcommands, positional arguments, and exit codes remain as specified.
- The module never imports from `ledgerlinc_ocr.pipeline` or `ledgerlinc_ocr.preprocessing` (harness/pipeline separation; constitution §I).
- The module MAY import from `ledgerlinc_ocr.validator` (read-only: schema loading + artifact validation).

Any change that would break the above is a breaking API change and MUST be accompanied by an amendment entry.
