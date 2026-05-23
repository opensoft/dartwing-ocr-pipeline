"""Per-document evaluator — orchestrates compare + gates + scoring for one folder.

v1.3.0 (feature 022) wires the deterministic semantic table quality gate
into this writer: every evaluation_document.json now carries
``document_pass_fail.semantic_table_quality_passed`` (MI-17 / Q20) and,
when a sidecar was found OR the gate landed on ``unevaluable``, the closed
``semantic_table_quality`` object (data-model §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from dartwing_ocr.evaluator.compare import (
    FieldResult,
    build_actual_view,
    build_expected_view,
    compare_field,
    extract_field,
)
from dartwing_ocr.evaluator.exceptions import (
    ContractSetVersionMismatchError,
    DocumentIdMismatchError,
)
from dartwing_ocr.evaluator.gates import (
    DocumentPassFail,
    overall_passed,
    review_routing_passed,
    vendor_identity_passed,
)
from dartwing_ocr.evaluator.filenames import EVAL_DOC_FILENAME
from dartwing_ocr.evaluator.io import read_json, write_json
from dartwing_ocr.evaluator.normalize import normalized_equal
from dartwing_ocr.evaluator.schema import (
    load_evaluation_document_schema,
    load_expected_schema,
    load_final_payload_schema,
    validate_against_schema,
)
from dartwing_ocr.evaluator.scoring import (
    CONTRACT_SET_VERSION,
    ComparisonSummary,
    SCORED_FIELDS,
    build_comparison_summary,
    compute_document_score,
    is_compatible_version,
)
from dartwing_ocr.evaluator.semantic_quality import run_semantic_quality_gate
from dartwing_ocr.evaluator.semantic_quality_report import SemanticQualityResult

# Local alias (keeps call sites private).
_EVAL_DOC_FILENAME = EVAL_DOC_FILENAME

# Per-document sidecar filename for the semantic quality gate (feature 022).
_SEMANTIC_TABLE_TRUTH_FILENAME = "semantic_table_truth.json"
_PREPROCESS_OUTPUT_FILENAME = "preprocess_output.json"

Difficulty = Literal["easy", "medium", "hard", "missing_name"]


# MI-17 / Q20 value-domain mapping for `document_pass_fail.semantic_table_quality_passed`.
_SEMANTIC_PASSED_VALUE_DOMAIN: dict[str, bool | None] = {
    "passed": True,
    "failed": False,
    "unevaluable": False,
    "not_applicable": None,
}


def _semantic_quality_passed_value(status: str) -> bool | None:
    """Map a SemanticQualityResult.status to the writer field value (MI-17 / Q20).

    Returns ``True`` / ``False`` / ``None``. Raises ``ValueError`` on an
    unknown status string (MI-11 invariant guard at the writer boundary).
    """
    try:
        return _SEMANTIC_PASSED_VALUE_DOMAIN[status]
    except KeyError as exc:
        raise ValueError(
            f"semantic_table_quality.status {status!r} is not in the closed "
            f"Q26 enum {sorted(_SEMANTIC_PASSED_VALUE_DOMAIN)}"
        ) from exc


def _semantic_quality_result_to_persistable(
    result: SemanticQualityResult,
) -> dict[str, Any] | None:
    """Serialize a :class:`SemanticQualityResult` to its on-disk JSON dict.

    Returns ``None`` when ``status == "not_applicable"`` (the
    ``semantic_table_quality`` key is OMITTED from the eval doc per
    data-model §7 / evaluator-output-contract.md Example D).

    For ``passed`` / ``failed`` / ``unevaluable``, emits the closed-shape
    dict with sorted keys at every nesting level so the result is
    deterministic regardless of the host JSON encoder's behavior (MI-16).
    """
    if result.status == "not_applicable":
        return None

    se = result.supporting_evidence
    # Supporting evidence is guaranteed present on passed / failed / unevaluable
    # by SemanticQualityResult invariants (semantic_quality_report.py).
    assert se is not None, "supporting_evidence missing on evaluable verdict"
    supporting_evidence = {
        "body_confidence_mean": se.body_confidence_mean,
        "body_confidence_min": se.body_confidence_min,
        "body_line_count": se.body_line_count,
        "body_token_count": se.body_token_count,
        "header_band_excluded": se.header_band_excluded,
    }

    # failed_checks is always present on passed / failed / unevaluable per
    # F5 resolution; empty list [] when passed or unevaluable; non-empty
    # when failed.
    failed_checks_list = []
    for fc in result.failed_checks or ():
        failed_checks_list.append(
            {
                "category": fc.category,
                "expected": fc.expected,
                "field": fc.field,
                "observed": fc.observed,
                "position_index": fc.position_index,
                "predicate": fc.predicate,
                "row_id": fc.row_id,
            }
        )

    out: dict[str, Any] = {
        "failed_checks": failed_checks_list,
        "status": result.status,
        "supporting_evidence": supporting_evidence,
    }

    # row_reasons is required when status == failed; omitted otherwise (MI-14).
    if result.status == "failed" and result.row_reasons:
        out["row_reasons"] = {
            row_id: {
                "categories": list(entry.categories),
                "reason": entry.reason,
            }
            for row_id, entry in result.row_reasons.items()
        }

    # cause / cause_detail only when status == unevaluable.
    if result.status == "unevaluable":
        if result.cause is not None:
            out["cause"] = result.cause
        if result.cause_detail is not None:
            out["cause_detail"] = result.cause_detail

    return out


@dataclass(frozen=True, slots=True)
class DocumentEvaluation:
    """Full in-memory representation of one document's evaluation (data-model §5).

    Carries the v1.3.0 (feature 022) semantic quality verdict alongside
    the vendor-identity verdict. ``semantic_quality_result`` is always
    present (never ``None``); when no sidecar was found, it carries a
    ``status == "not_applicable"`` verdict.
    """

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
    semantic_quality_result: SemanticQualityResult | None = None

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
        """Serializable dict matching evaluation_document.schema.json (drops internal fields).

        v1.3.0 additive output (feature 022, MI-17 / Q20):

        - ``document_pass_fail.semantic_table_quality_passed`` — always
          present; ``true`` / ``false`` / ``null`` per the status mapping.
        - ``semantic_table_quality`` — present when status ∈ {passed,
          failed, unevaluable}; absent when status == not_applicable.
        """
        # Vendor-identity portion preserved byte-identical to v1.2.0 (MI-22).
        document_pass_fail: dict[str, Any] = {
            "vendor_identity_passed": self.document_pass_fail.vendor_identity_passed,
            "review_routing_passed": self.document_pass_fail.review_routing_passed,
            "overall_passed": self.document_pass_fail.overall_passed,
        }

        # Semantic verdict — always include the additive
        # `semantic_table_quality_passed` field per MI-17 / Q20 / FR-017.
        if self.semantic_quality_result is not None:
            document_pass_fail["semantic_table_quality_passed"] = (
                _semantic_quality_passed_value(self.semantic_quality_result.status)
            )
        else:
            # Defensive default — should not occur on the writer path
            # since evaluate_document always populates this field.
            document_pass_fail["semantic_table_quality_passed"] = None

        out: dict[str, object] = {
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
            "document_pass_fail": document_pass_fail,
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

        # semantic_table_quality object — present only when sidecar found
        # or status == unevaluable (data-model §7 / evaluator-output-contract.md).
        if self.semantic_quality_result is not None:
            stq = _semantic_quality_result_to_persistable(
                self.semantic_quality_result
            )
            if stq is not None:
                out["semantic_table_quality"] = stq

        return out


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
    from dartwing_ocr.evaluator.outcomes import DocumentEvaluationOutcome

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

    # Feature 022 — semantic quality gate (data-model §13).
    # Always invoked once per document (FR-017): sidecar absent → status
    # = not_applicable WITHOUT reading preprocess_output.json. The gate
    # itself is CPU-only, no Paddle, no network (MI-1).
    sidecar_candidate = folder / _SEMANTIC_TABLE_TRUTH_FILENAME
    preprocess_candidate = folder / _PREPROCESS_OUTPUT_FILENAME
    semantic_result = run_semantic_quality_gate(
        preprocess_output_path=preprocess_candidate if preprocess_candidate.is_file() else None,
        sidecar_path=sidecar_candidate if sidecar_candidate.is_file() else None,
        folder_basename=folder.name,
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
        semantic_quality_result=semantic_result,
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
