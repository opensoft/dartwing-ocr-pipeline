"""Schema loading + validation for evidence-packet input and output."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ledgerlinc_ocr.evidence_packet.errors import PacketInvalid, PreprocessInputInvalid

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACT_ROOT = _REPO_ROOT / "contracts" / "stage1_vendor_identity" / "v1.2.0"
_PACKET_SCHEMA_PATH = _CONTRACT_ROOT / "evidence_packet.schema.json"
_PREPROCESS_SCHEMA_PATH = _CONTRACT_ROOT / "preprocess_output.schema.json"


@lru_cache(maxsize=1)
def _packet_validator() -> Draft202012Validator:
    schema = json.loads(_PACKET_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


@lru_cache(maxsize=1)
def _preprocess_validator() -> Draft202012Validator:
    schema = json.loads(_PREPROCESS_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _format_errors(validator: Draft202012Validator, artifact: dict[str, Any]) -> list[str]:
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors]


def validate_preprocess_input(preprocess_output: dict[str, Any]) -> None:
    messages = _format_errors(_preprocess_validator(), preprocess_output)
    if messages:
        raise PreprocessInputInvalid(
            "preprocess_output.json failed schema validation: " + "; ".join(messages)
        )


def validate_packet(packet: dict[str, Any]) -> None:
    messages = _format_errors(_packet_validator(), packet)
    if messages:
        raise PacketInvalid(
            "evidence_packet failed schema validation: " + "; ".join(messages)
        )
