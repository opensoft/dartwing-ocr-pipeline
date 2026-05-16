"""T033: stderr failure record shape across all non-zero exit codes."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest

from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.runner import Runner
from dartwing_ocr.pipeline.stages import default_preprocess

_STAGE_VOCAB = {
    "arguments",
    "input_validation",
    "preprocess",
    "extraction",
    "routing",
    "final_payload",
    "schema_validation",
}

_EXIT_NAMES = {
    "USAGE_ERROR",
    "INPUT_NOT_FOUND",
    "INVALID_PDF",
    "OUTPUT_IN_USE",
    "OUTPUT_PATH_NOT_USABLE",
    "PROCESSING_FAILURE",
    "SCHEMA_VALIDATION_FAILURE",
}

_REQUIRED_KEYS = {
    "exit_code",
    "exit_code_name",
    "stage",
    "message",
    "artifacts_written",
}


def _last_record(capsys: pytest.CaptureFixture[str]) -> dict:
    lines = capsys.readouterr().err.strip().splitlines()
    assert lines, "expected at least one stderr line"
    return json.loads(lines[-1])


def _assert_record_shape(rec: dict) -> None:
    assert set(rec.keys()) == _REQUIRED_KEYS
    assert rec["exit_code_name"] in _EXIT_NAMES
    assert rec["stage"] in _STAGE_VOCAB
    assert isinstance(rec["message"], str)
    assert isinstance(rec["artifacts_written"], list)


def test_usage_error_shape(capsys: pytest.CaptureFixture[str]):
    assert main([]) == 10
    _assert_record_shape(_last_record(capsys))


def test_input_not_found_shape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(
        [
            "run",
            "--input",
            str(tmp_path / "nope.pdf"),
            "--output-dir",
            str(tmp_path),
            "--document-id",
            "inv_001",
        ]
    )
    assert code == 11
    _assert_record_shape(_last_record(capsys))


def test_invalid_pdf_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"hello")
    code = main(
        [
            "run",
            "--input",
            str(p),
            "--output-dir",
            str(tmp_path),
            "--document-id",
            "inv_001",
        ]
    )
    assert code == 12
    _assert_record_shape(_last_record(capsys))


def test_output_in_use_shape(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(1, "easy")
    (folder / "preprocess_output.json").write_bytes(b"{}")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 13
    _assert_record_shape(_last_record(capsys))


def test_output_path_not_usable_shape(
    tmp_pdf_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    dest = tmp_path / "readonly"
    dest.mkdir()
    mode = dest.stat().st_mode
    try:
        os.chmod(dest, 0o555)  # NOSONAR S2612 — intentional: simulate non-writable directory to verify the StructuredFailureRecord path.
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
        os.chmod(dest, mode)
    assert code == 14
    _assert_record_shape(_last_record(capsys))


def test_processing_failure_shape(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    def boom(invocation: Any, produced: dict) -> dict:
        raise RuntimeError("boom")

    folder = tmp_document_folder(1, "easy")
    code = main(
        ["run", "--document-folder", str(folder)],
        runner=Runner(extraction=boom),
    )
    assert code == 20
    _assert_record_shape(_last_record(capsys))


def test_schema_validation_failure_shape(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(1, "easy")
    code = main(
        ["run", "--document-folder", str(folder)],
        runner=Runner(preprocess=lambda i, p: {"bad": "shape"}),
    )
    assert code == 30
    _assert_record_shape(_last_record(capsys))
