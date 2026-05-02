"""US2 acceptance: Trijunction slots are load-bearing, status-driven, forward-compatible."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.evidence_packet import assemble_from_preprocess

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"
_FIXTURE_NAMES = sorted(p.name for p in _FIXTURE_DIR.iterdir() if p.suffix == ".json")
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.2.0"
    / "evidence_packet.schema.json"
)


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_ac1_all_three_slots_present(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    sources = packet["ingestion_sources"]
    assert set(sources.keys()) == {"paddleocr_vl", "falcon_ocr", "falcon_perception"}
    for slot_name, slot in sources.items():
        assert set(slot.keys()) == {"enabled", "status", "payload"}, slot_name


@pytest.mark.parametrize("fixture_name", _FIXTURE_NAMES)
def test_ac2_status_driven_payload(fixture_name):
    data = json.loads((_FIXTURE_DIR / fixture_name).read_text())
    packet = assemble_from_preprocess(data)
    sources = packet["ingestion_sources"]

    for slot_name, slot in sources.items():
        if slot["status"] in {"failure", "not_implemented"}:
            assert slot["payload"] is None, slot_name
        elif slot_name == "paddleocr_vl" and slot["status"] == "success":
            assert slot["payload"] == {"kind": "structural"}, slot_name


def test_ac2_schema_permits_future_success_payload_on_any_slot():
    schema = json.loads(_SCHEMA_PATH.read_text())
    payload_def = schema["$defs"]["ingestion_source"]["properties"]["payload"]
    # Must be a oneOf that includes both null and an object-with-kind branch.
    assert "oneOf" in payload_def
    variants = payload_def["oneOf"]
    assert {"type": "null"} in variants
    object_variants = [v for v in variants if v.get("type") == "object"]
    assert object_variants, "schema must allow a non-null object payload"
    (object_variant,) = object_variants
    assert "kind" in object_variant.get("required", [])
