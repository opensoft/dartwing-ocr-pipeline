"""T045: Quickstart §2 and §3 developer paths exercised end-to-end."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def test_quickstart_section_2_document_folder(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["document_id"] == "inv_001"
    assert set(payload["artifacts"].keys()) == set(RESERVED_ARTIFACT_NAMES)


def test_quickstart_section_3_input_plus_output_dir(
    tmp_pdf_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    out = tmp_path / "my_output"
    out.mkdir()
    code = main(
        [
            "run",
            "--input",
            str(tmp_pdf_file),
            "--output-dir",
            str(out),
            "--document-id",
            "acme_001",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["document_id"] == "acme_001"
    for name in RESERVED_ARTIFACT_NAMES:
        assert (out / name).is_file()
