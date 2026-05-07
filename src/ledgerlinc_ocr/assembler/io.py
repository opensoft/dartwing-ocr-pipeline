"""Load + schema-validate helpers for the assembler (research Decision 4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ledgerlinc_ocr.assembler.errors import (
    InputSchemaInvalidError,
    InputUnreadableError,
    OutputSchemaInvalidError,
)
from ledgerlinc_ocr.validator import ArtifactName, load_contract_set

_ARTIFACT_BY_SCHEMA_NAME = {
    "edge_extraction_output": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision": ArtifactName.ROUTING_DECISION,
    "final_structured_payload": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
}

_SCHEMA_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _schema_for(name: str, *, version: str) -> dict[str, Any]:
    key = (version, name)
    if key not in _SCHEMA_CACHE:
        contract_set = load_contract_set(version)
        path = contract_set.artifact_schemas[_ARTIFACT_BY_SCHEMA_NAME[name]]
        _SCHEMA_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE[key]


def _format_errors(errors) -> str:
    msgs = []
    for err in errors:
        pointer = "/" + "/".join(str(p) for p in err.absolute_path)
        msgs.append(f"{pointer}: {err.message}")
    return "; ".join(msgs)


def load_json(path: Path, *, input_name: str) -> dict:
    """Read `path` and parse JSON. Raises `InputUnreadableError` on any failure.

    Non-UTF-8 bytes, truncated JSON, non-object roots, and OS read errors all
    classify as `unreadable_input` — FR-003b distinguishes this from
    `missing_input` (file absent) and `schema_invalid_input` (parses OK but
    violates its schema).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputUnreadableError(f"{input_name} at {path.name}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise InputUnreadableError(
            f"{input_name} at {path.name}: not valid UTF-8 ({exc.reason} at byte {exc.start})"
        ) from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputUnreadableError(
            f"{input_name} at {path.name}: not valid JSON ({exc.msg} at line {exc.lineno})"
        ) from exc
    if not isinstance(data, dict):
        raise InputUnreadableError(
            f"{input_name} at {path.name}: root must be an object"
        )
    return data


def validate_input(
    data: dict,
    schema_name: str,
    *,
    input_name: str,
    contract_set_version: str,
) -> None:
    """Raise `InputSchemaInvalidError` on any schema failure."""
    validator = Draft202012Validator(
        _schema_for(schema_name, version=contract_set_version)
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        raise InputSchemaInvalidError(
            f"{input_name}: schema-invalid — {_format_errors(errors)}"
        )


def validate_output(data: dict, *, contract_set_version: str) -> None:
    """Raise `OutputSchemaInvalidError` on any schema failure on the assembled payload."""
    validator = Draft202012Validator(
        _schema_for("final_structured_payload", version=contract_set_version)
    )
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        raise OutputSchemaInvalidError(
            f"final_structured_payload: schema-invalid — {_format_errors(errors)}"
        )
