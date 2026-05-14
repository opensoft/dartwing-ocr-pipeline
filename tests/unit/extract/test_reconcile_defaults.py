"""US5 T065 — reconcile() step 2 defaults missing sub-fields + records a warning."""

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


def _load_inputs():
    packet = json.loads((_US1_FIXTURE / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((_US1_FIXTURE / "voter_response_clean.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US1_FIXTURE / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return packet, parsed, config


def test_missing_tax_id_subfield_defaults_to_null_shape() -> None:
    packet, parsed, config = _load_inputs()
    parsed = copy.deepcopy(parsed)
    del parsed["vendor_candidate"]["tax_ids"]["vat_id"]

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    vat = out["vendor_candidate"]["tax_ids"]["vat_id"]
    assert vat == {"value": None, "confidence": 0.0, "evidence": []}


def test_missing_subfield_emits_warning_naming_field() -> None:
    packet, parsed, config = _load_inputs()
    parsed = copy.deepcopy(parsed)
    del parsed["invoice_header_fields"]["invoice_number"]

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    joined = "\n".join(out["warnings"])
    assert "invoice_header_fields/invoice_number" in joined


def test_missing_subfield_downgrades_status_to_partial() -> None:
    packet, parsed, config = _load_inputs()
    parsed = copy.deepcopy(parsed)
    del parsed["vendor_candidate"]["email"]

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    assert out["status"] == "partial"


def test_wrong_type_value_defaults_and_warns() -> None:
    packet, parsed, config = _load_inputs()
    parsed = copy.deepcopy(parsed)
    parsed["vendor_candidate"]["phone"] = {
        "value": 5551234567,  # integer, not string
        "confidence": 0.7,
        "evidence": [],
    }

    out = reconcile(
        packet=packet, parsed=parsed, config=config, now=_NOW, pipeline_version=_PV, repair_trail=[]
    )
    phone = out["vendor_candidate"]["phone"]
    assert phone["value"] is None
    assert any("vendor_candidate/phone" in w for w in out["warnings"])
