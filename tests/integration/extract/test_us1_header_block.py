"""US1 AC#4 — invoice_header_fields block has required scalars + total_amount shape."""

from __future__ import annotations

import re
from pathlib import Path

_EVIDENCE_ID = re.compile(r"^p\d+_[bl]\d+$")


def test_ac4_invoice_header_fields(us1_happy_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us1_happy_folder)
    hdr = payload["invoice_header_fields"]
    assert set(hdr.keys()) == {"invoice_number", "invoice_date", "total_amount"}

    for key in ("invoice_number", "invoice_date"):
        field = hdr[key]
        assert set(field.keys()) == {"value", "confidence", "evidence"}
        assert field["value"] is None or isinstance(field["value"], str)
        assert isinstance(field["confidence"], (int, float))
        assert 0.0 <= float(field["confidence"]) <= 1.0
        assert isinstance(field["evidence"], list)
        for eid in field["evidence"]:
            assert _EVIDENCE_ID.match(eid), f"bad evidence id: {eid!r}"

    total = hdr["total_amount"]
    assert set(total.keys()) == {"value", "currency", "confidence", "evidence"}
    assert total["value"] is None or isinstance(total["value"], (int, float))
    assert total["currency"] is None or isinstance(total["currency"], str)
    assert isinstance(total["confidence"], (int, float))
    assert 0.0 <= float(total["confidence"]) <= 1.0
    assert isinstance(total["evidence"], list)
    for eid in total["evidence"]:
        assert _EVIDENCE_ID.match(eid), f"bad evidence id: {eid!r}"

    dt = payload["document_type"]
    assert dt["value"] == "invoice"
    assert 0.0 <= float(dt["confidence"]) <= 1.0
