"""US3 AC#3 — malformed inputs exit 2 with no artifact written.

Covers clarification cases: encrypted, malformed, non-PDF (text file with
.pdf extension), and zero-page. Each MUST exit 2 and MUST NOT write an
artifact.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


def _run_cli(folder: Path) -> int:
    from ledgerlinc_ocr.preprocessing.cli import main

    return main(["--document-folder", str(folder)])


def _stage(tmp_path: Path, src: Path, folder_name: str) -> Path:
    folder = tmp_path / folder_name
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")
    return folder


def _assert_exit_2_no_artifact(tmp_path: Path, src: Path, folder_name: str) -> None:
    folder = _stage(tmp_path, src, folder_name)
    code = _run_cli(folder)
    assert code == 2, f"expected exit 2, got {code}"
    assert not (folder / "preprocess_output.json").exists(), (
        "artifact must not be written on malformed input"
    )
    leftovers = list(folder.glob("preprocess_output.json.tmp-*"))
    assert leftovers == [], f"no tmp files expected, found {leftovers}"


def test_ac3_encrypted_exits_2(tmp_path, us3_fixtures):
    _assert_exit_2_no_artifact(tmp_path, us3_fixtures["encrypted"], "inv_032")


def test_ac3_malformed_exits_2(tmp_path, us3_fixtures):
    _assert_exit_2_no_artifact(tmp_path, us3_fixtures["malformed"], "inv_033")


def test_ac3_non_pdf_exits_2(tmp_path, us3_fixtures):
    _assert_exit_2_no_artifact(tmp_path, us3_fixtures["non_pdf"], "inv_034")


def test_ac3_zero_page_exits_2(tmp_path, us3_fixtures):
    _assert_exit_2_no_artifact(tmp_path, us3_fixtures["zero_page"], "inv_035")


def test_ac3_missing_folder_exits_2(tmp_path):
    code = _run_cli(tmp_path / "does_not_exist")
    assert code == 2


def test_ac3_missing_pdf_exits_2(tmp_path):
    folder = tmp_path / "inv_999"
    folder.mkdir()
    code = _run_cli(folder)
    assert code == 2
    assert not (folder / "preprocess_output.json").exists()
