"""T014: Unit tests for the five ``scores`` values per FR-017.

Pinned formulas:
- ``company_name_score`` binary: 1.0 iff explicit+grounded, else 0.0.
- ``address_score`` denominator = 5 over {street_1, city, state, postal_code,
  country}; ``street_2`` does NOT contribute (research Decision 5).
- ``tax_id_score`` denominator = 4.
- ``contact_score`` denominator = 3 over {website, phone, email}.
- ``overall_vendor_identity_score`` = arithmetic mean of the four.

No confidence values should influence any score (FR-018).
"""
from __future__ import annotations

import pytest

from dartwing_ocr.router.scores import compute_scores


def _grounded(value="x", evidence_ids=("p0_b1",)):
    return {"value": value, "confidence": 0.0, "evidence": list(evidence_ids)}


def _null_field():
    return {"value": None, "confidence": 0.0, "evidence": []}


def _explicit_name():
    return {
        "value": "Acme", "present": True, "inferred": False,
        "confidence": 0.99, "evidence": ["p0_b1"],
    }


def _missing_name():
    return {
        "value": None, "present": False, "inferred": True,
        "confidence": 0.0, "evidence": [],
    }


def _all_null_vendor():
    return {
        "company_name": _missing_name(),
        "address": {slot: _null_field() for slot in (
            "street_1", "street_2", "city", "state", "postal_code", "country",
        )},
        "tax_ids": {slot: _null_field() for slot in (
            "ein", "state_tax_id", "vat_id", "other_tax_id",
        )},
        "website": _null_field(),
        "phone": _null_field(),
        "email": _null_field(),
    }


def _input(vc):
    return {"vendor_candidate": vc}


# -- company_name_score -----------------------------------------------------

def test_company_name_score_explicit_and_grounded_is_one():
    vc = _all_null_vendor()
    vc["company_name"] = _explicit_name()
    assert compute_scores(_input(vc))["company_name_score"] == 1.0


def test_company_name_score_inferred_true_is_zero():
    vc = _all_null_vendor()
    vc["company_name"] = {
        "value": "Guess", "present": False, "inferred": True,
        "confidence": 0.3, "evidence": ["p0_b1"],
    }
    assert compute_scores(_input(vc))["company_name_score"] == 0.0


def test_company_name_score_present_but_no_evidence_is_zero():
    vc = _all_null_vendor()
    vc["company_name"] = {
        "value": "Acme", "present": True, "inferred": False,
        "confidence": 0.99, "evidence": [],
    }
    assert compute_scores(_input(vc))["company_name_score"] == 0.0


# -- address_score ----------------------------------------------------------

def test_address_score_denominator_is_five_and_street_2_does_not_contribute():
    vc = _all_null_vendor()
    vc["address"]["street_1"] = _grounded("123 Main")
    vc["address"]["street_2"] = _grounded("Suite 5")
    vc["address"]["city"] = _grounded("Portland")
    assert compute_scores(_input(vc))["address_score"] == pytest.approx(2 / 5)


def test_address_score_all_five_grounded_is_one():
    vc = _all_null_vendor()
    for slot in ("street_1", "city", "state", "postal_code", "country"):
        vc["address"][slot] = _grounded()
    assert compute_scores(_input(vc))["address_score"] == 1.0


def test_address_score_all_null_is_zero():
    vc = _all_null_vendor()
    assert compute_scores(_input(vc))["address_score"] == 0.0


# -- tax_id_score -----------------------------------------------------------

def test_tax_id_score_denominator_is_four():
    vc = _all_null_vendor()
    vc["tax_ids"]["ein"] = _grounded()
    assert compute_scores(_input(vc))["tax_id_score"] == pytest.approx(1 / 4)


def test_tax_id_score_all_grounded_is_one():
    vc = _all_null_vendor()
    for slot in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
        vc["tax_ids"][slot] = _grounded()
    assert compute_scores(_input(vc))["tax_id_score"] == 1.0


# -- contact_score ----------------------------------------------------------

def test_contact_score_denominator_is_three():
    vc = _all_null_vendor()
    vc["website"] = _grounded()
    assert compute_scores(_input(vc))["contact_score"] == pytest.approx(1 / 3)


def test_contact_score_all_three_grounded_is_one():
    vc = _all_null_vendor()
    vc["website"] = _grounded()
    vc["phone"] = _grounded()
    vc["email"] = _grounded()
    assert compute_scores(_input(vc))["contact_score"] == 1.0


# -- overall_vendor_identity_score ------------------------------------------

def test_overall_is_arithmetic_mean_of_four():
    vc = _all_null_vendor()
    vc["company_name"] = _explicit_name()  # 1.0
    vc["address"]["city"] = _grounded()
    vc["address"]["state"] = _grounded()
    vc["address"]["postal_code"] = _grounded()
    # address_score = 3/5
    # tax_id_score = 0
    # contact_score = 0
    # overall = (1.0 + 0.6 + 0 + 0) / 4 = 0.4
    assert compute_scores(_input(vc))["overall_vendor_identity_score"] == pytest.approx(0.4)


def test_overall_all_null_is_zero():
    assert compute_scores(_input(_all_null_vendor()))["overall_vendor_identity_score"] == 0.0


def test_overall_all_grounded_is_one():
    vc = _all_null_vendor()
    vc["company_name"] = _explicit_name()
    for slot in ("street_1", "city", "state", "postal_code", "country"):
        vc["address"][slot] = _grounded()
    for slot in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
        vc["tax_ids"][slot] = _grounded()
    vc["website"] = _grounded()
    vc["phone"] = _grounded()
    vc["email"] = _grounded()
    assert compute_scores(_input(vc))["overall_vendor_identity_score"] == 1.0


# -- key order --------------------------------------------------------------

def test_scores_keys_in_schema_required_order():
    scores = compute_scores(_input(_all_null_vendor()))
    assert list(scores.keys()) == [
        "company_name_score",
        "address_score",
        "tax_id_score",
        "contact_score",
        "overall_vendor_identity_score",
    ]


# -- confidence-independence ------------------------------------------------

def test_scores_ignore_confidence_values():
    vc = _all_null_vendor()
    vc["company_name"] = _explicit_name()
    baseline = compute_scores(_input(vc))
    # Mutate every confidence number; scores must not move.
    vc["company_name"]["confidence"] = 0.01
    vc["address"]["city"]["confidence"] = 1.0  # still null, ignored
    with_different_conf = compute_scores(_input(vc))
    assert baseline == with_different_conf
