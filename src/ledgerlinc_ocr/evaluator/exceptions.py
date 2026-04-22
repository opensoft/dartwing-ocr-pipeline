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
