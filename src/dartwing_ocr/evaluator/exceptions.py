"""Evaluator exception hierarchy per contracts/module-api.md §Public exceptions."""

from __future__ import annotations


class EvaluatorError(Exception):
    """Base class for all hard errors raised by the evaluator."""


class ContractSetVersionMismatchError(EvaluatorError):
    """An input artifact carries a `contract_set_version` other than the pinned value."""


class DocumentIdMismatchError(EvaluatorError):
    """`expected.json` and `final_structured_payload.json` disagree on `document_id`."""


class SchemaValidationError(EvaluatorError):
    """An input or output artifact failed Draft 2020-12 schema validation."""


class EmptyCorpusError(EvaluatorError):
    """Corpus root contains no per-document folders with `expected.json`."""


class SemanticGateInvariantError(EvaluatorError):
    """Gate-time invariant violation in the semantic table quality gate (Q42 / MI-19 / R-022.14).

    Raised by feature 022's semantic quality gate when it detects an
    internal inconsistency that indicates an implementation bug rather
    than a bad input file — for example: the anchor function returning a
    span with inverted indices, the verdict aggregator producing a status
    string outside the closed Q26 enum, or
    ``normalize(normalize(x)) != normalize(x)`` for some input.

    This exception MUST propagate to the top level. Catching it and
    converting it to an ``unevaluable`` verdict is forbidden by MI-19:
    ``unevaluable`` is reserved exclusively for cases where a required
    INPUT file is absent, cannot be parsed as JSON, fails schema
    validation, or contains no readable body OCR (per Q31's four-step
    cascade in :mod:`dartwing_ocr.evaluator.semantic_quality`). When this
    exception fires, the affected document MUST be excluded from
    ``semantic_table_quality_metrics`` aggregation and no
    ``semantic_table_quality`` object is written for that document.
    """
