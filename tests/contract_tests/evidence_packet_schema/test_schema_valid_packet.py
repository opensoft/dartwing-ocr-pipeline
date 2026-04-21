"""T015: evidence_packet.schema.json accepts valid packets and rejects invalid ones."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = (
    _REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.1.0"
    / "evidence_packet.schema.json"
)
_FIXTURES = Path(__file__).parent / "fixtures"


def _load_validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_valid_minimal_packet_validates() -> None:
    validator = _load_validator()
    packet = json.loads((_FIXTURES / "valid_minimal_packet.json").read_text(encoding="utf-8"))
    validator.validate(packet)


def test_invalid_missing_ingestion_source_fails() -> None:
    validator = _load_validator()
    packet = json.loads(
        (_FIXTURES / "invalid_missing_ingestion_source.json").read_text(encoding="utf-8")
    )
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(packet)
    assert "falcon_perception" in str(excinfo.value)
