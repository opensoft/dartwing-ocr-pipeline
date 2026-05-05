"""US2 Acceptance Scenario 4: missing/invalid prerequisite hard-fail.

Spec User Story 2 Acceptance Scenario 4; FR-010; design.md CHK013/CHK057.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.cli import main


MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
    b"xref\n0 3\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000053 00000 n \n"
    b"trailer<</Size 3/Root 1 0 R>>\n"
    b"startxref\n100\n%%EOF\n"
)


def _empty_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "inv_003_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return folder


def test_missing_prerequisite_exits_input_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--start-at routing without preprocess_output.json -> exit 11 (INPUT_NOT_FOUND).

    No downstream artifact written.
    """
    folder = _empty_folder(tmp_path)
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "routing",
        "--stop-after", "routing",
        "--routing-profile", "stub",
    ])
    assert code == 11  # INPUT_NOT_FOUND
    err_lines = capsys.readouterr().err.strip().splitlines()
    record = json.loads(err_lines[-1])
    assert record["stage"] == "prerequisite_validation"
    assert "preprocess_output.json" in record["message"]
    # No downstream artifact exists.
    assert not (folder / "routing_decision.json").exists()


def test_invalid_prerequisite_exits_schema_validation_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """--start-at routing with malformed preprocess_output.json -> exit 30 (SCHEMA_VALIDATION_FAILURE)."""
    folder = _empty_folder(tmp_path)
    # Stage a malformed preprocess artifact: valid JSON, wrong shape.
    (folder / "preprocess_output.json").write_text(
        json.dumps({"this": "is not a valid preprocess_output"}),
        encoding="utf-8",
    )
    # Stage extraction artifact too (so the routing prerequisite chain
    # would normally pass past preprocess_output's existence check).
    (folder / "edge_extraction_output.json").write_text(
        json.dumps({"also": "invalid"}),
        encoding="utf-8",
    )
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "routing",
        "--stop-after", "routing",
        "--routing-profile", "stub",
    ])
    assert code == 30  # SCHEMA_VALIDATION_FAILURE
    err_lines = capsys.readouterr().err.strip().splitlines()
    record = json.loads(err_lines[-1])
    assert record["stage"] == "prerequisite_validation"
    # No downstream artifact written.
    assert not (folder / "routing_decision.json").exists()


def test_malformed_prerequisite_json_exits_schema_validation_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Unreadable/malformed prerequisite artifacts return a structured failure."""
    folder = _empty_folder(tmp_path)
    (folder / "preprocess_output.json").write_text("{", encoding="utf-8")

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "extract",
        "--stop-after", "extract",
        "--extract-profile", "stub",
    ])

    assert code == 30
    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["stage"] == "prerequisite_validation"
    assert "preprocess_output.json" in record["message"]
    assert "cannot read or parse artifact" in record["message"]
    assert not (folder / "edge_extraction_output.json").exists()


def test_missing_extraction_prereq_named_in_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """--start-at extract with no preprocess_output.json: message names the unmet prerequisite."""
    folder = _empty_folder(tmp_path)
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "extract",
        "--stop-after", "extract",
        "--extract-profile", "stub",
    ])
    assert code == 11
    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["stage"] == "prerequisite_validation"
    assert "preprocess_output.json" in record["message"]
