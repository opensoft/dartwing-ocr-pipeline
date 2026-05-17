"""Stage 1 vendor-identity evaluator & reporting package.

Public surface per `specs/007-evaluator/contracts/module-api.md`.
`evaluate_document` and `evaluate_corpus` are wired in by their owning story phases.
"""

from dartwing_ocr.evaluator.compare import FieldResult
from dartwing_ocr.evaluator.corpus import (
    ConsensusMetrics,
    DifficultyStats,
    DocumentListEntry,
    OverallMetrics,
    RunSummary,
    evaluate_corpus,
)
from dartwing_ocr.evaluator.document import DocumentEvaluation, evaluate_document
from dartwing_ocr.evaluator.exceptions import (
    ContractSetVersionMismatchError,
    DocumentIdMismatchError,
    EmptyCorpusError,
    EvaluatorError,
    SchemaValidationError,
)
from dartwing_ocr.evaluator.gates import DocumentPassFail
from dartwing_ocr.evaluator.outcomes import (
    DocumentEvaluationOutcome,
    RunSummaryOutcome,
)
from dartwing_ocr.evaluator.scoring import (
    CONTRACT_SET_VERSION,
    ComparisonSummary,
    ResultLabel,
)

__all__ = [
    "CONTRACT_SET_VERSION",
    "ComparisonSummary",
    "ConsensusMetrics",
    "ContractSetVersionMismatchError",
    "DifficultyStats",
    "DocumentEvaluation",
    "DocumentEvaluationOutcome",
    "DocumentIdMismatchError",
    "DocumentListEntry",
    "DocumentPassFail",
    "EmptyCorpusError",
    "EvaluatorError",
    "FieldResult",
    "evaluate_corpus",
    "evaluate_document",
    "OverallMetrics",
    "ResultLabel",
    "RunSummary",
    "RunSummaryOutcome",
    "SchemaValidationError",
]
