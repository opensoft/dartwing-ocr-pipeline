"""T036 / US3 AC#4: address_has_minimum_components iff city+state+postal_code
ALL grounded. No subset satisfies the minimum."""
from __future__ import annotations

import pytest

from ledgerlinc_ocr.router.checks import compute_checks


def _grounded(val):
    return {"value": val, "confidence": 0.9, "evidence": ["p0_b1"]}


def _null():
    return {"value": None, "confidence": 0.0, "evidence": []}


def _input_with_address(**grounded_slots):
    all_slots = {
        slot: _null()
        for slot in ("street_1", "street_2", "city", "state",
                     "postal_code", "country")
    }
    for slot, val in grounded_slots.items():
        all_slots[slot] = _grounded(val)
    return {
        "vendor_candidate": {
            "company_name": {
                "value": "Acme", "present": True, "inferred": False,
                "confidence": 0.9, "evidence": ["p0_b0"],
            },
            "address": all_slots,
            "tax_ids": {slot: _null() for slot in
                        ("ein", "state_tax_id", "vat_id", "other_tax_id")},
            "website": _null(),
            "phone": _null(),
            "email": _null(),
        }
    }


@pytest.mark.parametrize("slots,expected", [
    (("city",), False),
    (("state",), False),
    (("postal_code",), False),
    (("city", "state"), False),
    (("city", "postal_code"), False),
    (("state", "postal_code"), False),
    (("city", "state", "postal_code"), True),
])
def test_address_minimum_components(slots, expected):
    grounded = {s: f"val-{s}" for s in slots}
    checks = compute_checks(_input_with_address(**grounded))
    assert checks["address_has_minimum_components"] is expected
