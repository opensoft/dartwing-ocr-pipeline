"""T015: Unit tests for ``input_loader.load_and_validate``.

Maps the four hard-error conditions in FR-003 and the CLI contract to typed
exceptions. No filesystem fixtures — we build bytes inline via ``tmp_path``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.router.errors import (
    MalformedInputError,
    MissingInputError,
    UnreadableInputError,
    VersionDriftError,
)
from ledgerlinc_ocr.router.input_loader import load_and_validate

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "router"
GREEN_PATH = FIXTURE_DIR / "clean_explicit_name_full_identity.json"


def test_load_and_validate_success(tmp_path: Path):
    # Load the green-path fixture; must return a dict with vendor_candidate.
    data = load_and_validate(GREEN_PATH)
    assert isinstance(data, dict)
    assert data["contract_set_version"] == "1.0.0"
    assert data["vendor_candidate"]["company_name"]["present"] is True


def test_missing_file_raises_missing_input_error(tmp_path: Path):
    with pytest.raises(MissingInputError) as excinfo:
        load_and_validate(tmp_path / "nope.json")
    assert "does not exist" in excinfo.value.human_message


def test_path_is_directory_raises_missing_input_error(tmp_path: Path):
    (tmp_path / "subdir").mkdir()
    with pytest.raises(MissingInputError):
        load_and_validate(tmp_path / "subdir")


def test_non_utf8_bytes_raise_unreadable_input_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_bytes(b"\xff\xfe\x00\x00not-utf-8")
    with pytest.raises(UnreadableInputError):
        load_and_validate(p)


def test_malformed_json_raises_malformed_input_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json")
    with pytest.raises(MalformedInputError):
        load_and_validate(p)


def test_non_object_json_raises_malformed_input_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]")
    with pytest.raises(MalformedInputError):
        load_and_validate(p)


def test_schema_invalid_content_raises_malformed_input_error(tmp_path: Path):
    p = tmp_path / "bad.json"
    # Version is 1.0.0 but the shape is missing required top-level keys.
    p.write_text(json.dumps({"contract_set_version": "1.0.0"}))
    with pytest.raises(MalformedInputError):
        load_and_validate(p)


def test_version_drift_raises_version_drift_error(tmp_path: Path):
    data = json.loads(GREEN_PATH.read_text())
    data["contract_set_version"] = "0.9.0"
    p = tmp_path / "drifted.json"
    p.write_text(json.dumps(data))
    with pytest.raises(VersionDriftError) as excinfo:
        load_and_validate(p)
    assert "0.9.0" in excinfo.value.human_message


def test_version_drift_takes_precedence_over_schema(tmp_path: Path):
    # If version drift is detected, the error MUST name version drift even
    # though the document would also fail other checks.
    data = {"contract_set_version": "2.0.0"}
    p = tmp_path / "drifted.json"
    p.write_text(json.dumps(data))
    with pytest.raises(VersionDriftError):
        load_and_validate(p)
