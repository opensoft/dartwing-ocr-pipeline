"""T017 [US2] — flatten / strip evidence acceptance scenarios AS-1..AS-6."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ledgerlinc_ocr.assembler import Invocation, run

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


@pytest.fixture
def happy_folder(tmp_path: Path) -> Path:
    dst = tmp_path / "happy_grounded"
    shutil.copytree(FIXTURE_ROOT / "happy_grounded", dst)
    return dst


def _assert_no_evidence_anywhere(node) -> None:
    if isinstance(node, dict):
        assert "evidence" not in node, f"evidence key found at {list(node.keys())}"
        for v in node.values():
            _assert_no_evidence_anywhere(v)
    elif isinstance(node, list):
        for item in node:
            _assert_no_evidence_anywhere(item)


def test_output_has_zero_evidence_keys(happy_folder: Path):
    out_path = run(Invocation(document_folder=happy_folder))
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    _assert_no_evidence_anywhere(payload)


def test_populated_fields_emit_value_confidence_only(happy_folder: Path):
    out_path = run(Invocation(document_folder=happy_folder))
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    vc = payload["vendor_candidate"]
    # Populated scalar (email)
    assert set(vc["email"].keys()) == {"value", "confidence"}
    assert vc["email"]["value"] == "billing@acme.test"
    # Populated nested (address.city)
    assert set(vc["address"]["city"].keys()) == {"value", "confidence"}


def test_null_fields_survive_as_value_null_with_confidence(happy_folder: Path):
    out_path = run(Invocation(document_folder=happy_folder))
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    vc = payload["vendor_candidate"]
    # website is null in the fixture
    assert vc["website"] == {"value": None, "confidence": 0.0}
    assert vc["tax_ids"]["state_tax_id"] == {"value": None, "confidence": 0.0}


def test_company_name_keeps_four_keys(happy_folder: Path):
    out_path = run(Invocation(document_folder=happy_folder))
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    cn = payload["vendor_candidate"]["company_name"]
    assert set(cn.keys()) == {"value", "present", "inferred", "confidence"}
    assert cn["present"] is True
    assert cn["inferred"] is False


def test_invoice_header_fields_never_in_output(happy_folder: Path):
    out_path = run(Invocation(document_folder=happy_folder))
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "invoice_header_fields" not in payload
    # And nothing leaks into vendor_candidate either:
    vc_keys = set(payload["vendor_candidate"].keys())
    assert vc_keys == {"company_name", "address", "tax_ids", "website", "phone", "email"}


def test_present_inferred_not_recomputed_on_missing_fixture(tmp_path: Path):
    """missing_name_inferred has present=false, inferred=true — copy exactly."""
    dst = tmp_path / "missing_name_inferred"
    shutil.copytree(FIXTURE_ROOT / "missing_name_inferred", dst)
    out_path = run(Invocation(document_folder=dst))
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    cn = payload["vendor_candidate"]["company_name"]
    assert cn["present"] is False
    assert cn["inferred"] is True
