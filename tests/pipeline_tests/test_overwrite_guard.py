"""T017: --overwrite guard on reserved artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main


def test_preexisting_artifact_without_overwrite(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(1, "easy")
    artifact = folder / "preprocess_output.json"
    sentinel = b'{"sentinel":true}'
    artifact.write_bytes(sentinel)

    code = main(["run", "--document-folder", str(folder)])
    assert code == 13
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "OUTPUT_IN_USE"
    assert artifact.read_bytes() == sentinel


def test_overwrite_replaces(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    artifact = folder / "preprocess_output.json"
    artifact.write_bytes(b'{"sentinel":true}')

    code = main(["run", "--document-folder", str(folder), "--overwrite"])
    assert code == 0
    data = json.loads(artifact.read_text())
    assert "sentinel" not in data
    assert data["document_id"] == "inv_001_easy"


def test_non_reserved_files_never_touched(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    extra = folder / "notes.md"
    extra.write_text("keep me", encoding="utf-8")

    # Without overwrite (and without preexisting reserved artifacts): success
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    assert extra.read_text() == "keep me"
