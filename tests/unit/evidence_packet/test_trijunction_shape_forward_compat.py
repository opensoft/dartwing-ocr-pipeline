"""SC-005: a future Falcon-OCR success payload validates against the current schema."""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.2.0"
    / "evidence_packet.schema.json"
)

_VALID_MINIMAL_PACKET = (
    Path(__file__).resolve().parents[2]
    / "contract_tests"
    / "evidence_packet_schema"
    / "fixtures"
    / "valid_minimal_packet.json"
)


def test_future_falcon_ocr_success_payload_validates():
    packet = json.loads(_VALID_MINIMAL_PACKET.read_text())

    # Simulate a future Falcon OCR adapter wired in — status success with a
    # structured payload whose `kind` has never been seen before.
    packet["ingestion_sources"]["falcon_ocr"] = {
        "enabled": True,
        "status": "success",
        "payload": {
            "kind": "text_plus_spam_gate",
            "text": "hello",
            "spam_gate": {"flagged": False, "reason": None},
        },
    }

    schema = json.loads(_SCHEMA_PATH.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(packet), key=lambda e: list(e.absolute_path))
    assert errors == [], [
        "/".join(str(p) for p in err.absolute_path) + ": " + err.message
        for err in errors
    ]
