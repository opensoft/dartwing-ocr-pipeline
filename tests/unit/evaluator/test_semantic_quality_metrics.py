"""T046 (US3): unit tests for ``build_metrics_namespace`` (FR-018 / Q19 / Q36 / Q39).

Covers six cases from the Phase 5 task spec:

- (a) all eight ``semantic_table_quality_metrics`` fields populate from a
  mixed-status document list
- (b) ``semantic_evaluable_document_count == semantic_passed_document_count
  + semantic_failed_document_count``
- (c) ``semantic_table_quality_pass_rate`` rounded to 6 dp ROUND_HALF_EVEN
- (d) ``pass_rate == null`` when evaluable=0
- (e) ``semantic_failed_check_counts`` is an object keyed by the four
  kebab-case categories
- (f) calibration folders (non-matching ``CANONICAL_FOLDER_PATTERN``) appear
  in per-document entries but are EXCLUDED from aggregate counts (Q39 / MI-20)
"""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.semantic_quality_body_ocr import BodyOcrEvidence
from dartwing_ocr.evaluator.semantic_quality_metrics import build_metrics_namespace
from dartwing_ocr.evaluator.semantic_quality_report import (
    FailedCheck,
    RowReasonEntry,
    SemanticQualityResult,
    SupportingEvidence,
)


def _evidence(line_count: int = 1) -> SupportingEvidence:
    return SupportingEvidence(
        body_confidence_mean=0.97,
        body_confidence_min=0.94,
        body_line_count=line_count,
        body_token_count=line_count * 5,
        header_band_excluded=True,
    )


def _empty_evidence() -> SupportingEvidence:
    return SupportingEvidence(
        body_confidence_mean=0.0,
        body_confidence_min=0.0,
        body_line_count=0,
        body_token_count=0,
        header_band_excluded=False,
    )


def _passed_result() -> SemanticQualityResult:
    return SemanticQualityResult(
        status="passed",
        failed_checks=[],
        supporting_evidence=_evidence(),
    )


def _failed_result(*categories: str) -> SemanticQualityResult:
    failed = [
        FailedCheck(
            category=cat,
            row_id=f"row-{i + 1}",
            field="unit_price",
            expected="21.00",
            observed="$21:00",
            predicate="...",
            position_index=i,
        )
        for i, cat in enumerate(categories)
    ]
    row_reasons = {
        fc.row_id: RowReasonEntry(categories=[fc.category], reason="...")
        for fc in failed
    }
    return SemanticQualityResult(
        status="failed",
        failed_checks=failed,
        supporting_evidence=_evidence(),
        row_reasons=row_reasons,
    )


def _not_applicable_result() -> SemanticQualityResult:
    return SemanticQualityResult(
        status="not_applicable",
        failed_checks=None,
        supporting_evidence=None,
    )


def _unevaluable_result() -> SemanticQualityResult:
    return SemanticQualityResult(
        status="unevaluable",
        failed_checks=[],
        supporting_evidence=_empty_evidence(),
        cause="preprocess_output_missing",
    )


# ---------------------------------------------------------------------------
# (a) All 8 fields populate from a mixed-status document list
# ---------------------------------------------------------------------------


def test_a_all_eight_metric_fields_present_on_mixed_list() -> None:
    per_doc = [
        ("inv_001_hard", _failed_result("malformed-currency-shape")),
        ("inv_002_easy", _passed_result()),
        ("inv_003_medium", _not_applicable_result()),
        ("inv_004_hard", _unevaluable_result()),
    ]
    metrics = build_metrics_namespace(per_doc)

    expected_keys = {
        "semantic_applicable_document_count",
        "semantic_not_applicable_document_count",
        "semantic_evaluable_document_count",
        "semantic_passed_document_count",
        "semantic_failed_document_count",
        "semantic_unevaluable_document_count",
        "semantic_table_quality_pass_rate",
        "semantic_failed_check_counts",
    }
    assert set(metrics.keys()) == expected_keys


# ---------------------------------------------------------------------------
# (b) evaluable == passed + failed
# ---------------------------------------------------------------------------


def test_b_evaluable_count_equals_passed_plus_failed() -> None:
    per_doc = [
        ("inv_001_hard", _passed_result()),
        ("inv_002_easy", _passed_result()),
        ("inv_003_medium", _failed_result("missing-required-content")),
        ("inv_004_hard", _unevaluable_result()),
        ("inv_005_easy", _not_applicable_result()),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert (
        metrics["semantic_evaluable_document_count"]
        == metrics["semantic_passed_document_count"]
        + metrics["semantic_failed_document_count"]
    )


# ---------------------------------------------------------------------------
# (c) pass rate rounded to 6 dp ROUND_HALF_EVEN
# ---------------------------------------------------------------------------


def test_c_pass_rate_rounded_to_6_dp_round_half_even() -> None:
    # 1 / 3 = 0.333... → 0.333333 at 6 dp ROUND_HALF_EVEN
    per_doc = [
        ("inv_001_hard", _passed_result()),
        ("inv_002_easy", _failed_result("missing-required-content")),
        ("inv_003_medium", _failed_result("missing-required-content")),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert metrics["semantic_table_quality_pass_rate"] == pytest.approx(0.333333)


def test_c_pass_rate_zero_with_no_passes() -> None:
    per_doc = [
        ("inv_001_hard", _failed_result("missing-required-content")),
        ("inv_002_easy", _failed_result("missing-required-content")),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert metrics["semantic_table_quality_pass_rate"] == pytest.approx(0.0)


def test_c_pass_rate_one_with_all_passes() -> None:
    per_doc = [
        ("inv_001_hard", _passed_result()),
        ("inv_002_easy", _passed_result()),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert metrics["semantic_table_quality_pass_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# (d) pass_rate is null when evaluable == 0
# ---------------------------------------------------------------------------


def test_d_pass_rate_null_when_evaluable_zero() -> None:
    per_doc = [
        ("inv_001_hard", _not_applicable_result()),
        ("inv_002_easy", _unevaluable_result()),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert metrics["semantic_evaluable_document_count"] == 0
    assert metrics["semantic_table_quality_pass_rate"] is None


def test_d_pass_rate_null_when_empty_input() -> None:
    metrics = build_metrics_namespace([])
    assert metrics["semantic_evaluable_document_count"] == 0
    assert metrics["semantic_table_quality_pass_rate"] is None


# ---------------------------------------------------------------------------
# (e) semantic_failed_check_counts has all four kebab-case keys, defaulting to 0
# ---------------------------------------------------------------------------


def test_e_failed_check_counts_has_all_four_kebab_case_keys() -> None:
    per_doc = [("inv_001_hard", _passed_result())]
    metrics = build_metrics_namespace(per_doc)
    counts = metrics["semantic_failed_check_counts"]
    assert set(counts.keys()) == {
        "malformed-currency-shape",
        "missing-required-content",
        "row-text-coverage-gap",
        "row-alignment-failure",
    }
    # When no failures, all four default to 0.
    assert all(v == 0 for v in counts.values())


def test_e_failed_check_counts_aggregates_categories() -> None:
    """Multiple failed_checks across documents sum into the right buckets."""
    per_doc = [
        (
            "inv_001_hard",
            _failed_result(
                "malformed-currency-shape",
                "missing-required-content",
                "row-text-coverage-gap",
            ),
        ),
        (
            "inv_002_easy",
            _failed_result(
                "malformed-currency-shape",
                "row-alignment-failure",
            ),
        ),
    ]
    metrics = build_metrics_namespace(per_doc)
    counts = metrics["semantic_failed_check_counts"]
    assert counts["malformed-currency-shape"] == 2
    assert counts["missing-required-content"] == 1
    assert counts["row-text-coverage-gap"] == 1
    assert counts["row-alignment-failure"] == 1


# ---------------------------------------------------------------------------
# (f) Calibration folders excluded from aggregates per Q39 / MI-20
# ---------------------------------------------------------------------------


def test_f_calibration_folders_excluded_from_aggregates() -> None:
    """Q39 / MI-20: a folder whose basename does NOT match CANONICAL_FOLDER_PATTERN
    is calibration material. It MUST NOT contribute to any aggregate counter
    in semantic_table_quality_metrics."""
    per_doc = [
        ("inv_001_hard", _passed_result()),
        ("inv_002_easy", _failed_result("missing-required-content")),
        # Calibration folder — must NOT contribute to aggregates
        (
            "inv_024_hard_degraded_body",
            _failed_result("malformed-currency-shape", "row-text-coverage-gap"),
        ),
    ]
    metrics = build_metrics_namespace(per_doc)

    # Only the 2 scored folders contribute
    assert metrics["semantic_applicable_document_count"] == 2
    assert metrics["semantic_evaluable_document_count"] == 2
    assert metrics["semantic_passed_document_count"] == 1
    assert metrics["semantic_failed_document_count"] == 1
    assert metrics["semantic_not_applicable_document_count"] == 0
    assert metrics["semantic_unevaluable_document_count"] == 0

    # Calibration folder's two failed_checks must NOT appear in the counts
    counts = metrics["semantic_failed_check_counts"]
    assert counts["malformed-currency-shape"] == 0
    assert counts["row-text-coverage-gap"] == 0
    assert counts["missing-required-content"] == 1  # from inv_002_easy only
    assert counts["row-alignment-failure"] == 0


def test_f_calibration_folder_alone_yields_zero_aggregates() -> None:
    """A run containing ONLY calibration folders has zero aggregates and a
    null pass rate (Q39 / SC-009)."""
    per_doc = [
        ("inv_024_hard_degraded_body", _passed_result()),
        ("inv_099_super_special", _failed_result("missing-required-content")),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert metrics["semantic_applicable_document_count"] == 0
    assert metrics["semantic_evaluable_document_count"] == 0
    assert metrics["semantic_passed_document_count"] == 0
    assert metrics["semantic_failed_document_count"] == 0
    assert metrics["semantic_table_quality_pass_rate"] is None
    assert all(v == 0 for v in metrics["semantic_failed_check_counts"].values())


# ---------------------------------------------------------------------------
# Counter sanity tests on scored documents
# ---------------------------------------------------------------------------


def test_scored_counts_breakdown() -> None:
    per_doc = [
        ("inv_001_hard", _passed_result()),
        ("inv_002_easy", _passed_result()),
        ("inv_003_medium", _failed_result("missing-required-content")),
        ("inv_004_hard", _unevaluable_result()),
        ("inv_005_easy", _not_applicable_result()),
        ("inv_006_medium", _not_applicable_result()),
    ]
    metrics = build_metrics_namespace(per_doc)
    assert metrics["semantic_applicable_document_count"] == 4  # 2 passed + 1 failed + 1 unevaluable
    assert metrics["semantic_not_applicable_document_count"] == 2
    assert metrics["semantic_evaluable_document_count"] == 3  # 2 passed + 1 failed
    assert metrics["semantic_passed_document_count"] == 2
    assert metrics["semantic_failed_document_count"] == 1
    assert metrics["semantic_unevaluable_document_count"] == 1
    assert metrics["semantic_table_quality_pass_rate"] == pytest.approx(0.666667)


def test_pass_rate_is_python_float_not_decimal() -> None:
    """JSON encoder serializes Python floats as JSON numbers. The metrics
    builder MUST emit a float (or None) — not a Decimal — for the pass rate."""
    per_doc = [("inv_001_hard", _passed_result())]
    metrics = build_metrics_namespace(per_doc)
    rate = metrics["semantic_table_quality_pass_rate"]
    assert rate is None or isinstance(rate, float)


# ---------------------------------------------------------------------------
# Codex P2 PR #47 review fix (2026-05-23) — closed MI-12 category set
# ---------------------------------------------------------------------------


def test_unknown_failed_check_category_raises_value_error() -> None:
    """MI-12 closed kebab-case set: aggregator MUST raise on unknown categories.

    Per Sourcery + Copilot + Codex P2 review on PR #47: silently dropping
    unknown categories would mask upstream contract drift and undercount
    failures. The aggregator now raises ValueError citing the offending
    category, folder, and the closed-set inventory.
    """
    bad_check = _failed_check("not-a-real-category")
    bad_result = _failed_result_with_check(bad_check)
    per_doc = [("inv_001_hard", bad_result)]
    with pytest.raises(ValueError) as excinfo:
        build_metrics_namespace(per_doc)
    msg = str(excinfo.value)
    assert "unknown failed-check category" in msg
    assert "not-a-real-category" in msg
    assert "inv_001_hard" in msg


def _failed_check(category: str):
    """Build a FailedCheck stand-in with an arbitrary category string."""
    from dartwing_ocr.evaluator.semantic_quality_report import FailedCheck

    return FailedCheck(
        category=category,
        row_id="row-1",
        field="unit_price",
        expected="1.00",
        observed=None,
        predicate="test-only",
        position_index=0,
    )


def _failed_result_with_check(check):
    """Build a SemanticQualityResult with status=failed and the given check."""
    from dartwing_ocr.evaluator.semantic_quality_report import (
        SemanticQualityResult,
        SupportingEvidence,
    )

    return SemanticQualityResult(
        status="failed",
        failed_checks=[check],
        row_reasons={"row-1": {"categories": [check.category], "reason": "test"}},
        supporting_evidence=SupportingEvidence(
            body_confidence_mean=0.9,
            body_confidence_min=0.9,
            body_line_count=1,
            body_token_count=1,
            header_band_excluded=False,
        ),
        cause=None,
        cause_detail=None,
    )
