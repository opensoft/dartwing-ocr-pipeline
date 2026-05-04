"""Copilot review item 3: per_document[].folder echoes the raw token from
--documents-file, not the resolved absolute path.
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


def test_relative_token_echoed_verbatim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    docs_file = tmp_path / "corpus.txt"
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text("inv_001_easy\n", encoding="utf-8")

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # Raw token preserved -- not the resolved absolute path.
    assert summary["per_document"][0]["folder"] == "inv_001_easy"
    assert "/" not in summary["per_document"][0]["folder"]


def test_absolute_token_echoed_verbatim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    docs_file = tmp_path / "corpus.txt"
    folder = tmp_path / "inv_002_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text(f"{folder}\n", encoding="utf-8")

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # Absolute token also echoed verbatim.
    assert summary["per_document"][0]["folder"] == str(folder)


def test_per_document_failure_record_also_echoes_raw_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Folder field on failure records uses the raw token too."""
    docs_file = tmp_path / "corpus.txt"
    folder = tmp_path / "inv_003_easy"
    folder.mkdir()
    # No source.pdf -> per-doc failure under the new PDF check (item 2).
    docs_file.write_text("inv_003_easy\n", encoding="utf-8")

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code != 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    record = summary["per_document"][0]
    assert record["status"] == "failure"
    assert record["folder"] == "inv_003_easy"
