"""T027 [US4] — secondary_identifiers_found derivation and ordering."""

from __future__ import annotations

from dartwing_ocr.assembler.quality import (
    SECONDARY_ENUM_ORDER,
    derive_secondary_identifiers,
)


def _empty_field():
    return {"value": None, "confidence": 0.0, "evidence": []}


def _grounded_field(value="x", conf=0.5):
    return {"value": value, "confidence": conf, "evidence": ["p1_b0"]}


def _extractor(**vc_overrides) -> dict:
    vc = {
        "company_name": {
            "value": None, "present": False, "inferred": False,
            "confidence": 0.0, "evidence": [],
        },
        "address": {
            "street_1": _empty_field(), "street_2": _empty_field(),
            "city": _empty_field(), "state": _empty_field(),
            "postal_code": _empty_field(), "country": _empty_field(),
        },
        "tax_ids": {
            "ein": _empty_field(), "state_tax_id": _empty_field(),
            "vat_id": _empty_field(), "other_tax_id": _empty_field(),
        },
        "website": _empty_field(),
        "phone": _empty_field(),
        "email": _empty_field(),
    }
    vc.update(vc_overrides)
    return {"vendor_candidate": vc}


def test_full_address_included():
    ext = _extractor(address={
        "street_1": _empty_field(), "street_2": _empty_field(),
        "city": _grounded_field("X"), "state": _grounded_field("Y"),
        "postal_code": _grounded_field("Z"), "country": _empty_field(),
    })
    assert derive_secondary_identifiers(ext) == ["address"]


def test_partial_address_excluded():
    """Only city+state, no postal → address NOT included."""
    ext = _extractor(address={
        "street_1": _empty_field(), "street_2": _empty_field(),
        "city": _grounded_field("X"), "state": _grounded_field("Y"),
        "postal_code": _empty_field(), "country": _empty_field(),
    })
    assert derive_secondary_identifiers(ext) == []


def test_each_tax_id_slot_individually():
    for slot in ("ein", "state_tax_id", "vat_id", "other_tax_id"):
        ext = _extractor(tax_ids={
            "ein": _empty_field(), "state_tax_id": _empty_field(),
            "vat_id": _empty_field(), "other_tax_id": _empty_field(),
            slot: _grounded_field("X"),
        })
        assert derive_secondary_identifiers(ext) == [slot]


def test_each_contact_slot_individually():
    for slot in ("website", "phone", "email"):
        ext = _extractor(**{slot: _grounded_field("X")})
        assert derive_secondary_identifiers(ext) == [slot]


def test_enum_order_preserved_regardless_of_derivation_order():
    ext = _extractor(
        email=_grounded_field("a@b"),
        tax_ids={
            "ein": _grounded_field("ein-val"),
            "state_tax_id": _empty_field(),
            "vat_id": _grounded_field("vat-val"),
            "other_tax_id": _empty_field(),
        },
        address={
            "street_1": _empty_field(), "street_2": _empty_field(),
            "city": _grounded_field("X"), "state": _grounded_field("Y"),
            "postal_code": _grounded_field("Z"), "country": _empty_field(),
        },
    )
    assert derive_secondary_identifiers(ext) == ["address", "ein", "vat_id", "email"]


def test_expected_enum_order_constant():
    assert SECONDARY_ENUM_ORDER == [
        "address", "ein", "state_tax_id", "vat_id", "other_tax_id",
        "website", "phone", "email",
    ]
