"""T037 / US3 AC#5: at_least_one_tax_id_present requires evidence grounding.

Non-null value with empty evidence does NOT count. Multiple grounded tax_ids
still count as exactly one floor slot.
"""
from __future__ import annotations

import pytest

from dartwing_ocr.router.checks import compute_checks


def _null():
    return {"value": None, "confidence": 0.0, "evidence": []}


def _grounded(val):
    return {"value": val, "confidence": 0.9, "evidence": ["p0_b1"]}


def _value_without_evidence(val):
    return {"value": val, "confidence": 0.9, "evidence": []}


def _input_with_taxids(**tax_slots):
    all_taxids = {
        slot: _null()
        for slot in ("ein", "state_tax_id", "vat_id", "other_tax_id")
    }
    for slot, field in tax_slots.items():
        all_taxids[slot] = field
    return {
        "vendor_candidate": {
            "company_name": {
                "value": "Acme", "present": True, "inferred": False,
                "confidence": 0.9, "evidence": ["p0_b0"],
            },
            "address": {slot: _null() for slot in (
                "street_1", "street_2", "city", "state",
                "postal_code", "country")},
            "tax_ids": all_taxids,
            "website": _null(),
            "phone": _null(),
            "email": _null(),
        }
    }


def test_null_value_is_not_present():
    checks = compute_checks(_input_with_taxids())
    assert checks["at_least_one_tax_id_present"] is False


def test_value_without_evidence_is_not_present():
    checks = compute_checks(_input_with_taxids(
        ein=_value_without_evidence("12-3456789")
    ))
    assert checks["at_least_one_tax_id_present"] is False


def test_grounded_ein_is_present():
    checks = compute_checks(_input_with_taxids(ein=_grounded("12-3456789")))
    assert checks["at_least_one_tax_id_present"] is True


def test_multiple_grounded_taxids_still_one_floor_slot():
    # The check is a boolean — extra grounded IDs cannot multiply the slot.
    checks = compute_checks(_input_with_taxids(
        ein=_grounded("12-3456789"),
        vat_id=_grounded("GB123456789"),
    ))
    assert checks["at_least_one_tax_id_present"] is True


@pytest.mark.parametrize("slot", ["ein", "state_tax_id", "vat_id", "other_tax_id"])
def test_any_grounded_slot_satisfies(slot):
    checks = compute_checks(_input_with_taxids(**{slot: _grounded("x")}))
    assert checks["at_least_one_tax_id_present"] is True
