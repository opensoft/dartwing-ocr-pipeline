"""US1 AC#3 — vendor_candidate block has every required sub-field with correct shape."""

from __future__ import annotations

import re
from pathlib import Path

_EVIDENCE_ID = re.compile(r"^p\d+_[bl]\d+$")

_ADDRESS_FIELDS = ("street_1", "street_2", "city", "state", "postal_code", "country")
_TAX_FIELDS = ("ein", "state_tax_id", "vat_id", "other_tax_id")
_VCE_FIELDS = ("website", "phone", "email")


def _assert_scalar_shape(field: dict, path: str) -> None:
    assert set(field.keys()) == {"value", "confidence", "evidence"}, f"{path} keys {field.keys()}"
    assert field["value"] is None or isinstance(field["value"], str), path
    assert isinstance(field["confidence"], (int, float))
    assert 0.0 <= float(field["confidence"]) <= 1.0
    assert isinstance(field["evidence"], list)
    for eid in field["evidence"]:
        assert isinstance(eid, str) and _EVIDENCE_ID.match(eid), f"{path} bad evidence id {eid!r}"


def test_ac3_vendor_candidate_shape(us1_happy_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us1_happy_folder)
    vc = payload["vendor_candidate"]

    cn = vc["company_name"]
    assert set(cn.keys()) == {"value", "present", "inferred", "confidence", "evidence"}
    assert isinstance(cn["present"], bool)
    assert isinstance(cn["inferred"], bool)
    assert cn["present"] != cn["inferred"], "company_name must satisfy present XOR inferred"
    assert isinstance(cn["confidence"], (int, float))
    assert isinstance(cn["evidence"], list)
    for eid in cn["evidence"]:
        assert _EVIDENCE_ID.match(eid), f"bad evidence id: {eid!r}"

    addr = vc["address"]
    assert set(addr.keys()) == set(_ADDRESS_FIELDS)
    for key in _ADDRESS_FIELDS:
        _assert_scalar_shape(addr[key], f"address/{key}")

    tax = vc["tax_ids"]
    assert set(tax.keys()) == set(_TAX_FIELDS)
    for key in _TAX_FIELDS:
        _assert_scalar_shape(tax[key], f"tax_ids/{key}")

    for key in _VCE_FIELDS:
        _assert_scalar_shape(vc[key], f"vendor_candidate/{key}")
