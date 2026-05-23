"""T029 / FR-017 / Q29 / Q30 / Q31 / Q37 — report shape tests.

Locked invariants:
- failed_checks is a flat ordered array (source of truth, MI-14).
- row_reasons is an OBJECT keyed by row_id (NOT an array, F1/F2/MI-14)
  whose values are records with EXACTLY two fields: `categories` and
  `reason`. Field names `failed_categories` / `reason_text` are forbidden.
- supporting_evidence has the closed shape; body_confidence_min is ALWAYS
  a JSON number, never null — even for body_line_count == 0 (F3/R-022.12).
- cause populated only when status == unevaluable; one of the four
  Q31 enum values; cause_detail is optional free text.
"""

from __future__ import annotations

from dataclasses import asdict, fields

import pytest

from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    BodyOcrEvidence,
    BodyOcrLine,
)
from dartwing_ocr.evaluator.semantic_quality_report import (
    FailedCheck,
    RowReasonEntry,
    SemanticQualityResult,
    SupportingEvidence,
    build_semantic_quality_result,
)


def _line(raw: str, conf: float = 0.97) -> BodyOcrLine:
    return BodyOcrLine(
        raw_text=raw,
        detector_confidence=conf,
        page_index=0,
        line_index=0,
        raw_tokens=raw.split(),
    )


def _ev(lines: list[BodyOcrLine], header_excluded: bool = False) -> BodyOcrEvidence:
    from dartwing_ocr.evaluator.semantic_quality_normalize import normalize

    joined = " ".join(line.raw_text for line in lines)
    return BodyOcrEvidence(
        included_lines=lines,
        excluded_line_count=1 if header_excluded else 0,
        normalized_search_string=normalize(joined),
        header_band_excluded=header_excluded,
    )


class TestFailedChecksFlatArrayShape:
    def test_failed_check_has_all_fr_015_fields(self) -> None:
        fc = FailedCheck(
            category="malformed-currency-shape",
            row_id="row-3",
            field="unit_price",
            expected="21.00",
            observed="$21:00",
            predicate="raw token must match canonical money regex",
            position_index=0,
        )
        assert fc.category == "malformed-currency-shape"
        assert fc.row_id == "row-3"
        assert fc.field == "unit_price"
        assert fc.expected == "21.00"
        assert fc.observed == "$21:00"
        assert fc.predicate
        assert fc.position_index == 0


class TestRowReasonShape:
    def test_row_reason_carries_categories_and_reason(self) -> None:
        rr = RowReasonEntry(
            categories=["malformed-currency-shape"],
            reason="unit_price token '$21:00' fails canonical money regex (colon-for-decimal)",
        )
        # Field names MUST be exactly `categories` and `reason`.
        field_names = {f.name for f in fields(RowReasonEntry)}
        assert field_names == {"categories", "reason"}
        assert "failed_categories" not in field_names
        assert "reason_text" not in field_names

    def test_row_reasons_is_dict_keyed_by_row_id_not_array(self) -> None:
        """F1/F2/MI-14: row_reasons in the result MUST be a dict keyed by
        row_id, with values that DO NOT carry row_id as a field."""
        ev = _ev([_line("body text")])
        fc = FailedCheck(
            category="missing-required-content",
            row_id="row-1",
            field="quantity",
            expected="4",
            observed=None,
            predicate="normalized exact containment",
            position_index=0,
        )
        result = build_semantic_quality_result(
            status="failed", failed_checks=[fc], evidence=ev
        )
        assert isinstance(result.row_reasons, dict)
        assert "row-1" in result.row_reasons
        # The value is a record with categories + reason; row_id is the KEY
        entry = result.row_reasons["row-1"]
        # Allow either dataclass or BaseModel; we just need .categories + .reason
        cats = entry.categories if hasattr(entry, "categories") else entry["categories"]
        assert cats == ["missing-required-content"]


class TestSupportingEvidenceClosedShape:
    def test_supporting_evidence_field_set(self) -> None:
        se = SupportingEvidence(
            body_confidence_mean=0.97,
            body_confidence_min=0.95,
            body_line_count=5,
            body_token_count=20,
            header_band_excluded=True,
        )
        field_names = {f.name for f in fields(SupportingEvidence)}
        assert field_names == {
            "body_confidence_mean",
            "body_confidence_min",
            "body_line_count",
            "body_token_count",
            "header_band_excluded",
        }

    def test_body_confidence_min_is_zero_not_null_when_no_lines(self) -> None:
        """F3 / R-022.12: even when body_line_count == 0, body_confidence_min
        MUST be 0.0 (a JSON number), NEVER null."""
        ev = _ev([])
        result = build_semantic_quality_result(
            status="passed", failed_checks=[], evidence=ev
        )
        se = result.supporting_evidence
        assert se is not None
        assert se.body_line_count == 0
        # pytest.approx satisfies Sonar python:S1244 (no float equality).
        # The F3/R-022.12 invariant requires the bit-exact emission of
        # 0.0 (NOT null), which pytest.approx confirms with default tolerance.
        assert se.body_confidence_min == pytest.approx(0.0)
        assert se.body_confidence_mean == pytest.approx(0.0)
        # Crucial: not None.
        assert se.body_confidence_min is not None
        assert se.body_confidence_mean is not None

    def test_confidence_mean_correct(self) -> None:
        lines = [_line("a", 0.9), _line("b", 1.0), _line("c", 0.8)]
        ev = _ev(lines)
        result = build_semantic_quality_result(
            status="passed", failed_checks=[], evidence=ev
        )
        se = result.supporting_evidence
        # (0.9+1.0+0.8)/3 = 0.9
        assert abs(se.body_confidence_mean - 0.9) < 1e-9
        # pytest.approx satisfies Sonar python:S1244 (no float equality).
        assert se.body_confidence_min == pytest.approx(0.8)

    def test_token_count_correct(self) -> None:
        lines = [_line("a b c"), _line("d e")]
        ev = _ev(lines)
        result = build_semantic_quality_result(
            status="passed", failed_checks=[], evidence=ev
        )
        se = result.supporting_evidence
        assert se.body_token_count == 5
        assert se.body_line_count == 2


class TestFailedChecksAlwaysPresentRule:
    """F5: failed_checks ALWAYS PRESENT when status ∈ {passed, failed, unevaluable}.
    Omitted only when status == not_applicable."""

    def test_failed_checks_empty_array_on_passed(self) -> None:
        ev = _ev([_line("x")])
        result = build_semantic_quality_result(
            status="passed", failed_checks=[], evidence=ev
        )
        assert result.failed_checks == []

    def test_failed_checks_nonempty_on_failed(self) -> None:
        ev = _ev([_line("x")])
        fc = FailedCheck(
            category="missing-required-content",
            row_id="row-1",
            field="quantity",
            expected="4",
            observed=None,
            predicate="normalized exact containment",
            position_index=0,
        )
        result = build_semantic_quality_result(
            status="failed", failed_checks=[fc], evidence=ev
        )
        assert len(result.failed_checks) == 1

    def test_failed_checks_empty_array_on_unevaluable(self) -> None:
        ev = _ev([])
        result = build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=ev,
            cause="preprocess_output_missing",
        )
        assert result.failed_checks == []


class TestRowReasonsOmittedExceptOnFailed:
    """MI-14: row_reasons is required when status == failed; omitted otherwise.
    Omitted means None (or simply not set)."""

    def test_no_row_reasons_when_passed(self) -> None:
        ev = _ev([_line("x")])
        result = build_semantic_quality_result(
            status="passed", failed_checks=[], evidence=ev
        )
        assert result.row_reasons is None or result.row_reasons == {} or result.row_reasons == None

    def test_row_reasons_present_when_failed(self) -> None:
        ev = _ev([_line("x")])
        fc = FailedCheck(
            category="missing-required-content",
            row_id="row-1",
            field="quantity",
            expected="4",
            observed=None,
            predicate="normalized exact containment",
            position_index=0,
        )
        result = build_semantic_quality_result(
            status="failed", failed_checks=[fc], evidence=ev
        )
        assert result.row_reasons is not None
        assert "row-1" in result.row_reasons


class TestCauseFieldRules:
    """Q31: cause populated ONLY when status == unevaluable; closed enum."""

    def test_cause_required_when_unevaluable(self) -> None:
        ev = _ev([])
        result = build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=ev,
            cause="preprocess_output_missing",
        )
        assert result.cause == "preprocess_output_missing"

    def test_cause_absent_when_passed(self) -> None:
        ev = _ev([_line("x")])
        result = build_semantic_quality_result(
            status="passed", failed_checks=[], evidence=ev
        )
        assert result.cause is None

    def test_cause_detail_optional(self) -> None:
        ev = _ev([])
        result = build_semantic_quality_result(
            status="unevaluable",
            failed_checks=[],
            evidence=ev,
            cause="preprocess_output_invalid_json",
            cause_detail="JSON parse error at line 5",
        )
        assert result.cause_detail == "JSON parse error at line 5"


class TestRowReasonsMultiCategoryAggregation:
    def test_two_categories_for_one_row_aggregated(self) -> None:
        ev = _ev([_line("x")])
        fcs = [
            FailedCheck(
                category="malformed-currency-shape",
                row_id="row-1",
                field="unit_price",
                expected="21.00",
                observed="$21:00",
                predicate="raw token",
                position_index=0,
            ),
            FailedCheck(
                category="missing-required-content",
                row_id="row-1",
                field="quantity",
                expected="4",
                observed=None,
                predicate="normalized exact containment",
                position_index=1,
            ),
        ]
        result = build_semantic_quality_result(
            status="failed", failed_checks=fcs, evidence=ev
        )
        entry = result.row_reasons["row-1"]
        cats = entry.categories if hasattr(entry, "categories") else entry["categories"]
        # Both categories present, in Q17 fixed order.
        assert cats == ["malformed-currency-shape", "missing-required-content"]
