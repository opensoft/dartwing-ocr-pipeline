"""Unit tests for weight invariants and compute_document_score."""

from __future__ import annotations

from ledgerlinc_ocr.evaluator.compare import FieldResult
from ledgerlinc_ocr.evaluator.scoring import (
    FIELD_WEIGHTS,
    SCORED_FIELDS,
    ResultLabel,
    build_comparison_summary,
    compute_document_score,
)


def test_weights_sum_to_100() -> None:
    assert sum(FIELD_WEIGHTS.values()) == 100


def test_weights_keys_equal_scored_fields() -> None:
    assert set(FIELD_WEIGHTS) == set(SCORED_FIELDS)


def test_scored_fields_has_18_entries() -> None:
    assert len(SCORED_FIELDS) == 18


def _make_results(mapping: dict[str, ResultLabel]) -> tuple[FieldResult, ...]:
    out: list[FieldResult] = []
    for field in SCORED_FIELDS:
        label = mapping.get(field, ResultLabel.NOT_APPLICABLE)
        if label is ResultLabel.NOT_APPLICABLE:
            out.append(FieldResult(field_name=field, expected=None, actual=None, result=label))
            continue
        if label is ResultLabel.MISSING_PREDICTION:
            out.append(
                FieldResult(field_name=field, expected="x", actual=None, result=label)
            )
            continue
        if label is ResultLabel.UNEXPECTED_PREDICTION:
            out.append(
                FieldResult(field_name=field, expected=None, actual="x", result=label)
            )
            continue
        if field in {"company_name.present", "company_name.inferred", "manual_review_required"}:
            if label is ResultLabel.MATCH:
                out.append(
                    FieldResult(field_name=field, expected=True, actual=True, result=label)
                )
            else:
                out.append(
                    FieldResult(field_name=field, expected=True, actual=False, result=label)
                )
            continue
        out.append(
            FieldResult(field_name=field, expected="x", actual="x", result=label)
        )
    return tuple(out)


def test_all_match_document_score_is_one() -> None:
    results = _make_results({f: ResultLabel.MATCH for f in SCORED_FIELDS})
    assert compute_document_score(results) == 1.0


def test_all_not_applicable_returns_zero() -> None:
    results = _make_results({})
    assert compute_document_score(results) == 0.0


def test_hand_computed_mixed_labels() -> None:
    """Explicit hand-computed document score.

    Applicable fields:
    - company_name.value = MATCH (weight 20, value 1.0) = 20
    - company_name.present = MATCH (weight 8, value 1.0) = 8
    - company_name.inferred = MATCH (weight 8, value 1.0) = 8
    - address.city = MATCH (4, 1.0) = 4
    - address.state = MATCH (3, 1.0) = 3
    - address.postal_code = PARTIAL_MATCH (3, 0.5) = 1.5
    - tax_ids.ein = MISMATCH (8, 0.0) = 0
    - website = MATCH (6, 1.0) = 6
    - manual_review_required = MATCH (8, 1.0) = 8
    Denominator = 20+8+8+4+3+3+8+6+8 = 68
    Numerator  = 20+8+8+4+3+1.5+0+6+8 = 58.5
    Score = 58.5 / 68 = 0.860294...
    Rounded 6 = 0.860294
    """
    results = _make_results(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.city": ResultLabel.MATCH,
            "address.state": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.PARTIAL_MATCH,
            "tax_ids.ein": ResultLabel.MISMATCH,
            "website": ResultLabel.MATCH,
            "manual_review_required": ResultLabel.MATCH,
        }
    )
    score = compute_document_score(results)
    assert score == round(58.5 / 68, 6)


def test_comparison_summary_excludes_not_applicable() -> None:
    results = _make_results(
        {
            "company_name.value": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.PARTIAL_MATCH,
            "tax_ids.ein": ResultLabel.MISMATCH,
            "website": ResultLabel.MISSING_PREDICTION,
            "email": ResultLabel.UNEXPECTED_PREDICTION,
        }
    )
    summary = build_comparison_summary(results)
    assert summary.applicable_field_count == 5
    assert summary.matched_field_count == 1
    assert summary.mismatched_field_count == 1
    assert summary.missing_prediction_count == 1
    assert summary.unexpected_prediction_count == 1
    # partial = applicable - tallied = 5 - 4 = 1
    # field_accuracy = (1 + 0.5 * 1) / 5 = 0.3
    assert summary.field_accuracy == 0.3
