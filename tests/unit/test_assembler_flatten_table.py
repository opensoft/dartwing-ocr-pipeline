"""T018 [US2] — parameterized test over FIELDS_TO_FLATTEN."""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.assembler.flatten import FIELDS_TO_FLATTEN, flatten_vendor_candidate


def _make_extractor() -> dict:
    """Build a minimal extractor dict with every field in FIELDS_TO_FLATTEN populated."""
    return {
        "vendor_candidate": {
            "company_name": {
                "value": "X", "present": True, "inferred": False,
                "confidence": 0.9, "evidence": ["p1_b0"],
            },
            "address": {
                "street_1": {"value": "a", "confidence": 0.1, "evidence": ["p1_b1"]},
                "street_2": {"value": None, "confidence": 0.0, "evidence": []},
                "city": {"value": "b", "confidence": 0.2, "evidence": ["p1_b2"]},
                "state": {"value": "c", "confidence": 0.3, "evidence": ["p1_b3"]},
                "postal_code": {"value": "d", "confidence": 0.4, "evidence": ["p1_b4"]},
                "country": {"value": "e", "confidence": 0.5, "evidence": ["p1_b5"]},
            },
            "tax_ids": {
                "ein": {"value": "f", "confidence": 0.6, "evidence": ["p1_b6"]},
                "state_tax_id": {"value": "g", "confidence": 0.7, "evidence": ["p1_b7"]},
                "vat_id": {"value": "h", "confidence": 0.8, "evidence": ["p1_b8"]},
                "other_tax_id": {"value": "i", "confidence": 0.9, "evidence": ["p1_b9"]},
            },
            "website": {"value": "j", "confidence": 0.1, "evidence": ["p1_b10"]},
            "phone": {"value": "k", "confidence": 0.2, "evidence": ["p1_b11"]},
            "email": {"value": "l", "confidence": 0.3, "evidence": ["p1_b12"]},
        }
    }


@pytest.mark.parametrize("ext_path,final_path,kind", FIELDS_TO_FLATTEN)
def test_each_entry_produces_documented_shape(ext_path, final_path, kind):
    extractor = _make_extractor()
    vc = flatten_vendor_candidate(extractor)

    node = {"vendor_candidate": vc}
    for key in final_path:
        node = node[key]

    if kind == "value_confidence":
        assert set(node.keys()) == {"value", "confidence"}
    elif kind == "company_name":
        assert set(node.keys()) == {"value", "present", "inferred", "confidence"}
    else:
        pytest.fail(f"unexpected kind: {kind!r}")

    assert "evidence" not in node
