"""T024: --document-folder input handling."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def test_folder_with_source_pdf_succeeds(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    for name in RESERVED_ARTIFACT_NAMES:
        assert (folder / name).is_file()


def test_folder_without_source_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    code = main(["run", "--document-folder", str(folder)])
    assert code == 11
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "INPUT_NOT_FOUND"
    assert "source.pdf" in rec["message"]
    for name in RESERVED_ARTIFACT_NAMES:
        assert not (folder / name).exists()
