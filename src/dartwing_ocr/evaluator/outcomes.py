"""Pydantic outcome models for module API / CLI (data-model §11)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from dartwing_ocr.evaluator.corpus import RunSummary
from dartwing_ocr.evaluator.document import DocumentEvaluation


class DocumentEvaluationOutcome(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    ok: bool
    evaluation: DocumentEvaluation | None = None
    errors: list[str] = []
    warnings: list[str] = []
    output_path: Path | None = None


class RunSummaryOutcome(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    ok: bool
    summary: RunSummary | None = None
    per_document: list[DocumentEvaluationOutcome] = []
    errors: list[str] = []
    warnings: list[str] = []
    json_output_path: Path | None = None
    md_output_path: Path | None = None
