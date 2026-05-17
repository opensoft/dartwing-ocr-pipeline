"""Unit tests for compare_field: every ResultLabel path + FR-006 exclusions."""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.compare import FieldResult, compare_field
from dartwing_ocr.evaluator.scoring import ResultLabel


def test_null_both_sides_is_not_applicable() -> None:
    fr = compare_field("tax_ids.vat_id", None, None)
    assert fr.result is ResultLabel.NOT_APPLICABLE


def test_expected_non_null_actual_null_is_missing_prediction() -> None:
    fr = compare_field("tax_ids.ein", "12-3456789", None)
    assert fr.result is ResultLabel.MISSING_PREDICTION


def test_expected_null_actual_non_null_is_unexpected_prediction() -> None:
    fr = compare_field("website", None, "example.com")
    assert fr.result is ResultLabel.UNEXPECTED_PREDICTION


def test_exact_normalized_match() -> None:
    fr = compare_field("company_name.value", "Acme Widgets Inc.", "acme widgets inc")
    assert fr.result is ResultLabel.MATCH


def test_partial_match_on_postal() -> None:
    fr = compare_field("address.postal_code", "94110-1234", "94110")
    assert fr.result is ResultLabel.PARTIAL_MATCH


def test_mismatch_on_different_entity() -> None:
    fr = compare_field("company_name.value", "Acme Widgets", "Omega Gadgets")
    assert fr.result is ResultLabel.MISMATCH


# --- FR-006 exclusions: PARTIAL_MATCH forbidden on these fields ---------------


@pytest.mark.parametrize(
    "field",
    [
        "company_name.present",
        "company_name.inferred",
        "manual_review_required",
        "tax_ids.ein",
        "tax_ids.state_tax_id",
        "tax_ids.vat_id",
        "tax_ids.other_tax_id",
        "review_reason",
    ],
)
def test_no_partial_match_fields_return_only_match_or_mismatch(field: str) -> None:
    """For the no-partial fields, the comparator never emits PARTIAL_MATCH."""
    if field in {"company_name.present", "company_name.inferred", "manual_review_required"}:
        fr = compare_field(field, True, False)
        assert fr.result in (ResultLabel.MATCH, ResultLabel.MISMATCH)
    else:
        fr = compare_field(field, "12-3456789", "99-9999999")
        assert fr.result in (ResultLabel.MATCH, ResultLabel.MISMATCH)


def test_field_result_rejects_illegal_partial_match_on_boolean() -> None:
    with pytest.raises(ValueError, match="PARTIAL_MATCH not permitted"):
        FieldResult(
            field_name="manual_review_required",
            expected=True,
            actual=False,
            result=ResultLabel.PARTIAL_MATCH,
        )


def test_field_result_rejects_illegal_partial_match_on_tax_id() -> None:
    with pytest.raises(ValueError, match="PARTIAL_MATCH not permitted"):
        FieldResult(
            field_name="tax_ids.ein",
            expected="12-3456789",
            actual="12-3456780",
            result=ResultLabel.PARTIAL_MATCH,
        )


def test_field_result_rejects_illegal_partial_match_on_review_reason() -> None:
    with pytest.raises(ValueError, match="PARTIAL_MATCH not permitted"):
        FieldResult(
            field_name="review_reason",
            expected="company_name_inferred",
            actual="low_confidence",
            result=ResultLabel.PARTIAL_MATCH,
        )


def test_boolean_strict_equality() -> None:
    fr = compare_field("company_name.present", True, True)
    assert fr.result is ResultLabel.MATCH
    fr = compare_field("company_name.present", True, False)
    assert fr.result is ResultLabel.MISMATCH


def test_legacy_normalized_equal_kwarg_is_accepted_and_ignored() -> None:
    """Back-compat: callers can still pass normalized_equal, but the full rubric
    in normalize.classify_value is the authoritative source of truth."""
    called = {"count": 0}

    def bogus(field_name: str, a, b) -> bool:
        called["count"] += 1
        return False  # Should be ignored.

    fr = compare_field(
        "company_name.value",
        "Acme",
        "Acme",
        normalized_equal=bogus,
    )
    assert fr.result is ResultLabel.MATCH
    assert called["count"] == 0
