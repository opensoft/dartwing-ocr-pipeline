"""FR-017 + Edge Cases: library + CLI behavior on missing/invalid preprocess input."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ledgerlinc_ocr.evidence_packet import (
    PreprocessInputInvalid,
    PreprocessInputMissing,
    assemble_from_folder,
)


def _run_cli(folder: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.evidence_packet", str(folder)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout.strip())
    return result.returncode, payload


def test_missing_file_exit_2(tmp_path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    with pytest.raises(PreprocessInputMissing):
        assemble_from_folder(folder)
    code, payload = _run_cli(folder)
    assert code == 2
    assert payload["status"] == "error"
    assert payload["kind"] == "input_missing"


def test_invalid_schema_exit_3(tmp_path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    bad = {
        "contract_set_version": "1.0.0",
        "pipeline_version": "stage1-edge-v0.1",
        # missing document_id, source_type, etc.
    }
    (folder / "preprocess_output.json").write_text(json.dumps(bad))
    with pytest.raises(PreprocessInputInvalid):
        assemble_from_folder(folder)
    code, payload = _run_cli(folder)
    assert code == 3
    assert payload["kind"] == "input_invalid"


def test_non_json_exit_2(tmp_path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "preprocess_output.json").write_bytes(b"\x00\x01not-json\xff")
    with pytest.raises(PreprocessInputMissing):
        assemble_from_folder(folder)
    code, payload = _run_cli(folder)
    assert code == 2
    assert payload["kind"] == "input_missing"
