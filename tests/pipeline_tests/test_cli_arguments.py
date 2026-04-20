"""T013: argument parsing and subcommand dispatch."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.cli import main


def _last_stderr_line(capsys: pytest.CaptureFixture[str]) -> dict:
    err = capsys.readouterr().err.strip().splitlines()
    return json.loads(err[-1])


def test_no_subcommand_exits_usage_error(capsys: pytest.CaptureFixture[str]):
    code = main([])
    assert code == 10
    rec = _last_stderr_line(capsys)
    assert rec["exit_code"] == 10
    assert rec["stage"] == "arguments"


def test_run_with_neither_input_nor_folder(
    capsys: pytest.CaptureFixture[str],
):
    code = main(["run"])
    assert code == 10
    rec = _last_stderr_line(capsys)
    assert rec["exit_code_name"] == "USAGE_ERROR"
    assert rec["stage"] == "arguments"


def test_run_with_both_input_and_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(
        ["run", "--input", str(tmp_path / "a.pdf"), "--document-folder", str(tmp_path)]
    )
    assert code == 10


def test_unknown_argument(capsys: pytest.CaptureFixture[str]):
    code = main(["run", "--nope"])
    assert code == 10
    rec = _last_stderr_line(capsys)
    assert rec["stage"] == "arguments"


def test_invalid_log_level(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    code = main(
        [
            "run",
            "--document-folder",
            str(tmp_path),
            "--log-level",
            "invalid",
        ]
    )
    assert code == 10


def test_uninstalled_contract_set_version(
    tmp_pdf_file: Path, capsys: pytest.CaptureFixture[str]
):
    code = main(
        [
            "run",
            "--input",
            str(tmp_pdf_file),
            "--contract-set-version",
            "99.9.9",
        ]
    )
    assert code == 10
    rec = _last_stderr_line(capsys)
    assert rec["stage"] == "arguments"
    assert "99.9.9" in rec["message"]
