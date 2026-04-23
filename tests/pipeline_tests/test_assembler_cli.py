"""T046 — CLI integration."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.assembler", *args],
        capture_output=True, text=True,
    )


def test_help_exits_zero():
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "document-folder" in result.stdout


def test_missing_document_folder_argparse_error():
    result = _run_cli()
    assert result.returncode == 2
    assert "document-folder" in result.stderr


def test_successful_run_no_stdout(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    result = _run_cli("--document-folder", str(folder))
    assert result.returncode == 0
    assert result.stdout == ""
    assert (folder / "final_structured_payload.json").exists()


def test_pipeline_version_override(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    result = _run_cli(
        "--document-folder", str(folder),
        "--pipeline-version", "009-final-payload@9.9.9",
    )
    assert result.returncode == 0
    data = json.loads((folder / "final_structured_payload.json").read_text(encoding="utf-8"))
    assert data["pipeline_version"] == "009-final-payload@9.9.9"
