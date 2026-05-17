"""T026 [US4] — overall_vendor_confidence formula (Decision 6)."""

from __future__ import annotations

import pytest

from dartwing_ocr.assembler.quality import (
    compute_overall_vendor_confidence,
    derive_secondary_identifiers,
)


def _vc(
    *,
    company_conf: float = 0.0,
    city: tuple[str | None, float, list[str]] = (None, 0.0, []),
    state: tuple[str | None, float, list[str]] = (None, 0.0, []),
    postal: tuple[str | None, float, list[str]] = (None, 0.0, []),
    email: tuple[str | None, float, list[str]] = (None, 0.0, []),
) -> dict:
    def f(triplet):
        v, c, e = triplet
        return {"value": v, "confidence": c, "evidence": e}

    return {
        "vendor_candidate": {
            "company_name": {
                "value": None, "present": False, "inferred": False,
                "confidence": company_conf, "evidence": [],
            },
            "address": {
                "street_1": f((None, 0.0, [])),
                "street_2": f((None, 0.0, [])),
                "city": f(city),
                "state": f(state),
                "postal_code": f(postal),
                "country": f((None, 0.0, [])),
            },
            "tax_ids": {
                "ein": f((None, 0.0, [])),
                "state_tax_id": f((None, 0.0, [])),
                "vat_id": f((None, 0.0, [])),
                "other_tax_id": f((None, 0.0, [])),
            },
            "website": f((None, 0.0, [])),
            "phone": f((None, 0.0, [])),
            "email": f(email),
        }
    }


def test_all_null_yields_zero():
    ext = _vc(company_conf=0.0)
    secondary = derive_secondary_identifiers(ext)
    assert secondary == []
    assert compute_overall_vendor_confidence(ext, secondary) == pytest.approx(0.0)


def test_company_only_yields_half_company_conf():
    ext = _vc(company_conf=0.8)
    secondary = derive_secondary_identifiers(ext)
    assert compute_overall_vendor_confidence(ext, secondary) == pytest.approx(0.4)


def test_grounded_company_plus_address_plus_email():
    ext = _vc(
        company_conf=1.0,
        city=("X", 0.9, ["p1_b0"]),
        state=("Y", 0.9, ["p1_b0"]),
        postal=("Z", 0.9, ["p1_b0"]),
        email=("a@b", 0.8, ["p1_b1"]),
    )
    secondary = derive_secondary_identifiers(ext)
    assert secondary == ["address", "email"]
    addr_mean = 0.9
    expected = round(0.5 * 1.0 + 0.5 * ((addr_mean + 0.8) / 2.0), 4)
    assert compute_overall_vendor_confidence(ext, secondary) == expected


def test_result_is_rounded_to_four_decimals():
    ext = _vc(company_conf=0.12345)
    secondary = derive_secondary_identifiers(ext)
    got = compute_overall_vendor_confidence(ext, secondary)
    # 0.5 * 0.12345 + 0.0 = 0.061725 → round(_, 4) = 0.0617
    assert got == pytest.approx(0.0617)


def test_result_is_clipped_to_unit_interval():
    # company_conf=2.0 violates schema but the clip is a defensive property.
    ext = _vc(company_conf=2.0)
    got = compute_overall_vendor_confidence(ext, derive_secondary_identifiers(ext))
    assert got == pytest.approx(1.0)
