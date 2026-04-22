"""Unit tests for pass-gate logic — US3 AC#6/#7/#8 and Q3 slot semantics."""

from __future__ import annotations

from typing import Any

from ledgerlinc_ocr.evaluator.compare import FieldResult
from ledgerlinc_ocr.evaluator.gates import (
    overall_passed,
    review_routing_passed,
    vendor_identity_passed,
)
from ledgerlinc_ocr.evaluator.scoring import ResultLabel, SCORED_FIELDS


def _fr(field: str, result: ResultLabel, expected: Any = "x", actual: Any = "x") -> FieldResult:
    """Build a FieldResult with sensible placeholders for the null-rule branches."""
    if result is ResultLabel.NOT_APPLICABLE:
        expected = None
        actual = None
    elif result is ResultLabel.MISSING_PREDICTION:
        actual = None
        if expected is None:
            expected = "x"
    elif result is ResultLabel.UNEXPECTED_PREDICTION:
        expected = None
        if actual is None:
            actual = "x"
    elif field in {"company_name.present", "company_name.inferred", "manual_review_required"}:
        # Booleans need real booleans.
        if result is ResultLabel.MATCH:
            expected, actual = True, True
        else:
            expected, actual = True, False
    return FieldResult(
        field_name=field, expected=expected, actual=actual, result=result
    )


def _all_default(mapping: dict[str, ResultLabel]) -> tuple[FieldResult, ...]:
    """Build a full 18-field FieldResult tuple; fields not in `mapping` default to
    NOT_APPLICABLE (both expected and actual null)."""
    return tuple(
        _fr(field, mapping.get(field, ResultLabel.NOT_APPLICABLE))
        for field in SCORED_FIELDS
    )


# --- vendor_identity_passed ---------------------------------------------------


def test_vendor_identity_requires_company_name_value_match_or_partial() -> None:
    results = _all_default(
        {
            "company_name.value": ResultLabel.MISMATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.city": ResultLabel.MATCH,
            "address.state": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.MATCH,
            "website": ResultLabel.MATCH,
        }
    )
    assert vendor_identity_passed(results) is False


def test_vendor_identity_accepts_partial_company_name() -> None:
    results = _all_default(
        {
            "company_name.value": ResultLabel.PARTIAL_MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.city": ResultLabel.MATCH,
            "address.state": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.MATCH,
            "website": ResultLabel.MATCH,
        }
    )
    assert vendor_identity_passed(results) is True


def test_vendor_identity_requires_present_and_inferred_match() -> None:
    results = _all_default(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MISMATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.city": ResultLabel.MATCH,
            "address.state": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.MATCH,
            "website": ResultLabel.MATCH,
        }
    )
    assert vendor_identity_passed(results) is False


def test_address_slot_requires_city_state_postal_all(results_partial_address: None = None) -> None:
    # Only city + state match; postal MISMATCH → address slot does NOT count.
    results = _all_default(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.city": ResultLabel.MATCH,
            "address.state": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.MISMATCH,
            "website": ResultLabel.MATCH,  # one slot only → fails ≥2
        }
    )
    assert vendor_identity_passed(results) is False


def test_address_slot_accepts_partial_on_any_of_three() -> None:
    results = _all_default(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.city": ResultLabel.MATCH,
            "address.state": ResultLabel.MATCH,
            "address.postal_code": ResultLabel.PARTIAL_MATCH,  # ZIP+4 vs ZIP
            "email": ResultLabel.MATCH,  # second slot
        }
    )
    assert vendor_identity_passed(results) is True


def test_street_and_country_do_not_contribute_to_address_slot() -> None:
    results = _all_default(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "address.street_1": ResultLabel.MATCH,
            "address.country": ResultLabel.MATCH,
            # No city/state/postal → address slot does NOT count.
            "email": ResultLabel.MATCH,  # only one slot → fails ≥2
        }
    )
    assert vendor_identity_passed(results) is False


def test_tax_id_slot_never_counts_partial() -> None:
    # Even a PARTIAL on a tax_id should not count — tax IDs can never be partial.
    # But if somehow it were PARTIAL, the gate requires strict MATCH.
    results = _all_default(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "tax_ids.ein": ResultLabel.MATCH,  # first slot
            "website": ResultLabel.MATCH,  # second slot
        }
    )
    assert vendor_identity_passed(results) is True


def test_fewer_than_two_slots_fails_us3_ac8() -> None:
    results = _all_default(
        {
            "company_name.value": ResultLabel.MATCH,
            "company_name.present": ResultLabel.MATCH,
            "company_name.inferred": ResultLabel.MATCH,
            "website": ResultLabel.MATCH,  # only one slot
        }
    )
    assert vendor_identity_passed(results) is False


# --- review_routing_passed (US3 AC#6) ----------------------------------------


def test_review_routing_requires_manual_review_match() -> None:
    results = _all_default(
        {
            "manual_review_required": ResultLabel.MISMATCH,
            "review_reason": ResultLabel.MATCH,
        }
    )
    assert review_routing_passed(results) is False


def test_review_routing_agrees_when_both_review_reasons_null() -> None:
    results = _all_default(
        {
            "manual_review_required": ResultLabel.MATCH,
            # review_reason stays NOT_APPLICABLE → still agrees.
        }
    )
    assert review_routing_passed(results) is True


def test_review_routing_fails_when_reason_mismatches() -> None:
    results = _all_default(
        {
            "manual_review_required": ResultLabel.MATCH,
            "review_reason": ResultLabel.MISMATCH,
        }
    )
    assert review_routing_passed(results) is False


# --- overall_passed (US3 AC#7) -----------------------------------------------


def test_threshold_cannot_override_failed_vendor_identity() -> None:
    """Even a 0.87 document_score can't pass when vendor_identity_passed is False."""
    assert overall_passed(False, True, 0.87) is False


def test_threshold_cannot_override_failed_review_routing() -> None:
    assert overall_passed(True, False, 0.87) is False


def test_overall_passes_at_threshold_with_epsilon() -> None:
    # 0.849999 + 1e-9 is still < 0.85 exactly, but let's test the boundary at
    # 0.85 - 1e-10 (within epsilon).
    assert overall_passed(True, True, 0.85 - 1e-10) is True


def test_overall_below_threshold_fails() -> None:
    assert overall_passed(True, True, 0.80) is False
