"""US6 Acceptance Scenario 5: cold single-document mode keeps the
existing 002-cli-contract stdout shape exactly.

Research R-010. Verifies no `kind` field, no run_summary line in cold mode.
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


def test_cold_mode_stdout_exactly_one_line_no_kind_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 0
    out_lines = capsys.readouterr().out.strip().splitlines()
    # Cold mode emits exactly one stdout line (the 002 success summary).
    assert len(out_lines) == 1
    record = json.loads(out_lines[0])
    assert "kind" not in record
    assert "schema_version" not in record
    assert record["document_id"] == "inv_001_easy"


def test_cold_mode_with_on_failure_flag_is_no_op(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """R-010: --on-failure is accepted but is a no-op in cold mode."""
    folder = tmp_path / "inv_002_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    code = main([
        "run",
        "--document-folder", str(folder),
        "--on-failure", "continue",
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 0
    out_lines = capsys.readouterr().out.strip().splitlines()
    # Still exactly one line, no run_summary.
    assert len(out_lines) == 1
    assert "kind" not in json.loads(out_lines[0])
