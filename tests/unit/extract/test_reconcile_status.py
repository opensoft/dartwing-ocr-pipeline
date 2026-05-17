"""US5 T066 — reconcile() step 7 status truth table (R-008).

Covers:
  - Clean inputs → "success".
  - Any soft-bit (defaulted | evidence_dropped | repaired) with some grounded
    evidence → "partial".
  - All-null + all-empty-evidence → "failure".
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from dartwing_ocr.extract.config import load_voter_config
from dartwing_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"

_NOW = datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC)
_PV = "0.0.0-test+fixture"


def _load():
    packet = json.loads((_US1_FIXTURE / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((_US1_FIXTURE / "voter_response_clean.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US1_FIXTURE / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return packet, parsed, config


def _all_null_response() -> dict:
    scalar = {"value": None, "confidence": 0.0, "evidence": []}
    return {
        "document_type": {"value": None, "confidence": 0.0},
        "vendor_candidate": {
            "company_name": dict(scalar),
            "address": {
                k: dict(scalar) for k in
                ("street_1", "street_2", "city", "state", "postal_code", "country")
            },
            "tax_ids": {
                k: dict(scalar) for k in
                ("ein", "state_tax_id", "vat_id", "other_tax_id")
            },
            "website": dict(scalar),
            "phone": dict(scalar),
            "email": dict(scalar),
        },
        "invoice_header_fields": {
            "invoice_number": dict(scalar),
            "invoice_date": dict(scalar),
            "total_amount": {"value": None, "currency": None, "confidence": 0.0, "evidence": []},
        },
    }


def test_clean_inputs_yield_success() -> None:
    packet, parsed, config = _load()
    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "success"
    assert out["warnings"] == []


def test_repaired_bit_with_grounded_evidence_yields_partial() -> None:
    packet, parsed, config = _load()
    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV,
        repair_trail=["stripped markdown code fence"],
    )
    assert out["status"] == "partial"
    assert any("repaired" in w for w in out["warnings"])


def test_defaulted_bit_with_grounded_evidence_yields_partial() -> None:
    packet, parsed, config = _load()
    parsed = copy.deepcopy(parsed)
    del parsed["vendor_candidate"]["tax_ids"]["vat_id"]

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "partial"


def test_evidence_dropped_bit_yields_partial() -> None:
    packet, parsed, config = _load()
    parsed = copy.deepcopy(parsed)
    parsed["invoice_header_fields"]["invoice_number"]["evidence"] = ["p1_lZZZ"]  # unresolved

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "partial"


def test_all_null_and_empty_evidence_yields_failure() -> None:
    packet, _, config = _load()
    parsed = _all_null_response()
    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "failure"
    assert out["warnings"], "failure status must carry at least one explanatory warning"


def test_packet_warnings_alone_yield_partial() -> None:
    """FR-023: any input-side partiality (including packet.warnings) must cap
    output at status='partial' even when all ingestion_sources are green."""
    packet, parsed, config = _load()
    packet = copy.deepcopy(packet)
    packet["warnings"] = ["some input warning"]
    # Sanity: ensure every ingestion_source is currently green (not failure).
    for src in (packet.get("ingestion_sources") or {}).values():
        assert src.get("status") != "failure"

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "partial"
    assert any("input preprocessing was partial" in n for n in out["extraction_notes"])


def test_document_type_coercion_yields_partial() -> None:
    """Coercing a non-invoice document_type to 'invoice' is a silent rewrite;
    it must flip the partiality bit so status drops from success to partial."""
    packet, parsed, config = _load()
    parsed = copy.deepcopy(parsed)
    parsed["document_type"] = {"value": "receipt", "confidence": 0.9}

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "partial"
    assert out["document_type"]["value"] == "invoice"
    assert any("document_type coerced" in n for n in out["extraction_notes"])
