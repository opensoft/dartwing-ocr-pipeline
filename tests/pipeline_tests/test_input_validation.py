"""T016: input validation exit codes."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def _last_record(capsys: pytest.CaptureFixture[str]) -> dict:
    err = capsys.readouterr().err.strip().splitlines()
    return json.loads(err[-1])


def test_missing_input_pdf(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    missing = tmp_path / "nope.pdf"
    code = main(
        [
            "run",
            "--input",
            str(missing),
            "--output-dir",
            str(tmp_path),
            "--document-id",
            "inv_001",
        ]
    )
    assert code == 11
    rec = _last_record(capsys)
    assert rec["exit_code_name"] == "INPUT_NOT_FOUND"
    assert rec["stage"] == "input_validation"
    # No artifacts written
    for name in RESERVED_ARTIFACT_NAMES:
        assert not (tmp_path / name).exists()


def test_non_pdf_file_returns_invalid_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    not_pdf = tmp_path / "file.pdf"
    not_pdf.write_bytes(b"Hello, world!\n")
    code = main(
        [
            "run",
            "--input",
            str(not_pdf),
            "--output-dir",
            str(tmp_path),
            "--document-id",
            "inv_001",
        ]
    )
    assert code == 12
    rec = _last_record(capsys)
    assert rec["exit_code_name"] == "INVALID_PDF"


def test_missing_destination_folder(
    tmp_pdf_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    missing_dest = tmp_path / "not_a_folder"
    code = main(
        [
            "run",
            "--input",
            str(tmp_pdf_file),
            "--output-dir",
            str(missing_dest),
            "--document-id",
            "inv_001",
        ]
    )
    assert code == 11
    rec = _last_record(capsys)
    assert rec["exit_code_name"] == "INPUT_NOT_FOUND"


def test_read_only_destination_folder(
    tmp_pdf_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    dest = tmp_path / "readonly"
    dest.mkdir()
    original_mode = dest.stat().st_mode
    try:
        os.chmod(dest, 0o555)  # NOSONAR S2612 — intentional: simulate non-writable directory to exercise the OUTPUT_PATH_NOT_USABLE error path.
        code = main(
            [
                "run",
                "--input",
                str(tmp_pdf_file),
                "--output-dir",
                str(dest),
                "--document-id",
                "inv_001",
            ]
        )
    finally:
        os.chmod(dest, original_mode)
    assert code == 14
    rec = _last_record(capsys)
    assert rec["exit_code_name"] == "OUTPUT_PATH_NOT_USABLE"


def test_symlink_to_non_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    target = tmp_path / "real.txt"
    target.write_bytes(b"not a pdf\n")
    link = tmp_path / "link.pdf"
    link.symlink_to(target)
    code = main(
        [
            "run",
            "--input",
            str(link),
            "--output-dir",
            str(tmp_path),
            "--document-id",
            "inv_001",
        ]
    )
    assert code == 12
