"""Per-document evaluator — orchestrates compare + gates + scoring for one folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ledgerlinc_ocr.evaluator.compare import (
    FieldResult,
    build_actual_view,
    build_expected_view,
    compare_field,
    extract_field,
)
from ledgerlinc_ocr.evaluator.exceptions import (
    ContractSetVersionMismatchError,
    DocumentIdMismatchError,
)
from ledgerlinc_ocr.evaluator.gates import (
    DocumentPassFail,
    overall_passed,
    review_routing_passed,
    vendor_identity_passed,
)
from ledgerlinc_ocr.evaluator.filenames import EVAL_DOC_FILENAME
from ledgerlinc_ocr.evaluator.io import read_json, write_json
from ledgerlinc_ocr.evaluator.normalize import normalized_equal
from ledgerlinc_ocr.evaluator.schema import (
    load_evaluation_document_schema,
    load_expected_schema,
    load_final_payload_schema,
    validate_against_schema,
)
from ledgerlinc_ocr.evaluator.scoring import (
    CONTRACT_SET_VERSION,
    ComparisonSummary,
    SCORED_FIELDS,
    build_comparison_summary,
    compute_document_score,
    is_compatible_version,
)

# Local alias (keeps call sites private).
_EVAL_DOC_FILENAME = EVAL_DOC_FILENAME

Difficulty = Literal["easy", "medium", "hard", "missing_name"]


@dataclass(frozen=True, slots=True)
class DocumentEvaluation:
    """Full in-memory representation of one document's evaluation (data-model §5)."""

    contract_set_version: str
    document_id: str
    difficulty: Difficulty
    challenge_tags: tuple[str, ...]
    comparison_summary: ComparisonSummary
    document_pass_fail: DocumentPassFail
    field_results: tuple[FieldResult, ...]
    notes: tuple[str, ...]
    document_score: float
    folder_path: Path

    def __post_init__(self) -> None:
        if not is_compatible_version(self.contract_set_version, CONTRACT_SET_VERSION):
            raise ValueError(
                f"contract_set_version must be compatible with "
                f"{CONTRACT_SET_VERSION!r} (same major, minor ≤ pinned); "
                f"got {self.contract_set_version!r}"
            )
        names = tuple(f.field_name for f in self.field_results)
        if names != SCORED_FIELDS:
            raise ValueError(
                "field_results must be ordered and named per SCORED_FIELDS; "
                f"got {names}"
            )

    def to_persistable_dict(self) -> dict[str, object]:
        """Serializable dict matching evaluation_document.schema.json (drops internal fields)."""
        return {
            "contract_set_version": self.contract_set_version,
            "document_id": self.document_id,
            "difficulty": self.difficulty,
            "challenge_tags": list(self.challenge_tags),
            "comparison_summary": {
                "applicable_field_count": self.comparison_summary.applicable_field_count,
                "matched_field_count": self.comparison_summary.matched_field_count,
                "mismatched_field_count": self.comparison_summary.mismatched_field_count,
                "missing_prediction_count": self.comparison_summary.missing_prediction_count,
                "unexpected_prediction_count": self.comparison_summary.unexpected_prediction_count,
                "field_accuracy": self.comparison_summary.field_accuracy,
            },
            "document_pass_fail": {
                "vendor_identity_passed": self.document_pass_fail.vendor_identity_passed,
                "review_routing_passed": self.document_pass_fail.review_routing_passed,
                "overall_passed": self.document_pass_fail.overall_passed,
            },
            "field_results": {
                fr.field_name: {
                    "expected": fr.expected,
                    "actual": fr.actual,
                    "result": fr.result.value,
                }
                for fr in self.field_results
            },
            "notes": list(self.notes),
        }


def evaluate_document(
    folder: Path,
    *,
    contract_set_version: str | None = None,
) -> "DocumentEvaluationOutcome":  # type: ignore[name-defined]  # noqa: F821
    """Evaluate a single per-document folder.

    Reads `expected.json` and `final_structured_payload.json`, schema-validates
    both, checks `contract_set_version` and `document_id` integrity, builds
    per-field results in `SCORED_FIELDS` order, writes `evaluation_document.json`.

    Raises `EvaluatorError` subclasses on any hard error; no output is written in
    that case (FR-020).
    """
    from ledgerlinc_ocr.evaluator.outcomes import DocumentEvaluationOutcome

    folder = Path(folder)
    pinned_version = contract_set_version or CONTRACT_SET_VERSION

    expected_path = folder / "expected.json"
    payload_path = folder / "final_structured_payload.json"

    expected = read_json(expected_path)
    payload = read_json(payload_path)

    validate_against_schema(
        expected,
        load_expected_schema(pinned_version),
        source=expected_path,
        artifact_label="expected.json",
    )
    validate_against_schema(
        payload,
        load_final_payload_schema(pinned_version),
        source=payload_path,
        artifact_label="final_structured_payload.json",
    )

    exp_version = expected.get("contract_set_version")
    pay_version = payload.get("contract_set_version")
    if not is_compatible_version(exp_version, pinned_version):
        raise ContractSetVersionMismatchError(
            f"{expected_path}: contract_set_version {exp_version!r} is not compatible "
            f"with pinned {pinned_version!r} (same major, minor ≤ pinned)"
        )
    if not is_compatible_version(pay_version, pinned_version):
        raise ContractSetVersionMismatchError(
            f"{payload_path}: contract_set_version {pay_version!r} is not compatible "
            f"with pinned {pinned_version!r} (same major, minor ≤ pinned)"
        )

    exp_id = expected["document_id"]
    pay_id = payload["document_id"]
    if exp_id != pay_id:
        raise DocumentIdMismatchError(
            f"document_id mismatch: expected.json={exp_id!r}, "
            f"final_structured_payload.json={pay_id!r} at {folder}"
        )

    expected_view = build_expected_view(expected)
    actual_view = build_actual_view(payload)

    field_results_list: list[FieldResult] = []
    for field_name in SCORED_FIELDS:
        exp_value = extract_field(expected_view, field_name)
        act_value = extract_field(actual_view, field_name)
        field_results_list.append(
            compare_field(
                field_name,
                exp_value,
                act_value,
                normalized_equal=normalized_equal,
            )
        )
    field_results = tuple(field_results_list)

    summary = build_comparison_summary(field_results)
    doc_score = compute_document_score(field_results)
    vi_ok = vendor_identity_passed(field_results)
    rr_ok = review_routing_passed(
        field_results,
        missing_name=(expected.get("difficulty") == "missing_name"),
    )
    overall_ok = overall_passed(vi_ok, rr_ok, doc_score)
    pass_fail = DocumentPassFail(
        vendor_identity_passed=vi_ok,
        review_routing_passed=rr_ok,
        overall_passed=overall_ok,
    )

    evaluation = DocumentEvaluation(
        contract_set_version=pinned_version,
        document_id=exp_id,
        difficulty=expected["difficulty"],
        challenge_tags=tuple(expected.get("challenge_tags", [])),
        comparison_summary=summary,
        document_pass_fail=pass_fail,
        field_results=field_results,
        notes=(),
        document_score=doc_score,
        folder_path=folder,
    )

    persistable = evaluation.to_persistable_dict()
    validate_against_schema(
        persistable,
        load_evaluation_document_schema(pinned_version),
        source=folder / _EVAL_DOC_FILENAME,
        artifact_label=_EVAL_DOC_FILENAME,
    )

    output_path = folder / _EVAL_DOC_FILENAME
    write_json(output_path, persistable)

    return DocumentEvaluationOutcome(
        ok=True,
        evaluation=evaluation,
        output_path=output_path,
    )
