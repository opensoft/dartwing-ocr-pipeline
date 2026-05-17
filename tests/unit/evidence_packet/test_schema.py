"""T023: schema loader caching + typed-error propagation."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from dartwing_ocr.evidence_packet import schema as schema_mod
from dartwing_ocr.evidence_packet.errors import PacketInvalid, PreprocessInputInvalid

_FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "contract_tests"
    / "evidence_packet_schema"
    / "fixtures"
)
_PREPROCESS_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"


def test_packet_validator_is_cached() -> None:
    schema_mod._packet_validator.cache_clear()
    schema_mod._preprocess_validator.cache_clear()
    a = schema_mod._packet_validator()
    b = schema_mod._packet_validator()
    assert a is b


def test_preprocess_validator_is_cached() -> None:
    schema_mod._packet_validator.cache_clear()
    schema_mod._preprocess_validator.cache_clear()
    a = schema_mod._preprocess_validator()
    b = schema_mod._preprocess_validator()
    assert a is b


def test_corrupted_packet_raises_packet_invalid_with_path() -> None:
    packet = json.loads((_FIXTURES / "valid_minimal_packet.json").read_text(encoding="utf-8"))
    packet = copy.deepcopy(packet)
    del packet["ingestion_sources"]["falcon_perception"]
    with pytest.raises(PacketInvalid) as excinfo:
        schema_mod.validate_packet(packet)
    assert "falcon_perception" in str(excinfo.value)


def test_corrupted_preprocess_input_raises_preprocess_input_invalid() -> None:
    # A minimal malformed preprocess_output: missing required top-level key.
    bad_input: dict = {
        "contract_set_version": "1.0.0",
        # intentionally missing pipeline_version, document_id, etc.
    }
    with pytest.raises(PreprocessInputInvalid) as excinfo:
        schema_mod.validate_preprocess_input(bad_input)
    assert "pipeline_version" in str(excinfo.value) or "required" in str(excinfo.value)


def test_preprocess_input_validator_accepts_nullable_confidence() -> None:
    preprocess = json.loads(
        (_PREPROCESS_FIXTURES / "minimal_valid.json").read_text(encoding="utf-8")
    )
    preprocess["pages"][0]["blocks"][0]["confidence"] = None
    preprocess["pages"][0]["raw_ocr_lines"][0]["confidence"] = None

    schema_mod.validate_preprocess_input(preprocess)


def test_packet_validator_accepts_nullable_structural_confidence() -> None:
    packet = json.loads((_FIXTURES / "valid_minimal_packet.json").read_text(encoding="utf-8"))
    packet = copy.deepcopy(packet)
    packet["pages"][0]["blocks"][0]["confidence"] = None
    packet["pages"][0]["raw_ocr_lines"][0]["confidence"] = None

    schema_mod.validate_packet(packet)
