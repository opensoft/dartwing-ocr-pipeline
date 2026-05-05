"""Copilot review item 2: warm-corpus mode applies cold-path PDF
existence/type checks before constructing per-document invocations.

Without these checks the all-stub default-preprocess callable would
emit success artifacts for folders that lack a usable source.pdf.
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


def _build_corpus(tmp_path: Path, *, with_pdf: bool, pdf_bytes: bytes = MINIMAL_PDF_BYTES) -> tuple[Path, Path]:
    docs_file = tmp_path / "corpus.txt"
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    if with_pdf:
        (folder / "source.pdf").write_bytes(pdf_bytes)
    docs_file.write_text("inv_001_easy\n", encoding="utf-8")
    return docs_file, folder


def test_warm_corpus_missing_source_pdf_reports_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Missing source.pdf must surface as INPUT_NOT_FOUND, not silent stub success."""
    docs_file, folder = _build_corpus(tmp_path, with_pdf=False)
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == int(__import__("ledgerlinc_ocr.pipeline.exit_codes", fromlist=["ExitCode"]).ExitCode.INPUT_NOT_FOUND)
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])
    assert summary["documents_failed"] == 1
    assert summary["documents_succeeded"] == 0
    record = summary["per_document"][0]
    assert record["status"] == "failure"
    assert record["document_id"] == "inv_001"
    assert record["failed_stage"] == "corpus_validation"
    assert "source.pdf" in record["message"]
    # No stub success artifacts must have been emitted for this folder.
    assert not (folder / "preprocess_output.json").exists()
    assert not (folder / "edge_extraction_output.json").exists()


def test_warm_corpus_non_pdf_source_reports_invalid_pdf(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A source.pdf whose magic-byte check fails must surface as INVALID_PDF."""
    docs_file, folder = _build_corpus(tmp_path, with_pdf=True, pdf_bytes=b"not a pdf at all")
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    from ledgerlinc_ocr.pipeline.exit_codes import ExitCode
    assert code == int(ExitCode.INVALID_PDF)
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])
    record = summary["per_document"][0]
    assert record["status"] == "failure"
    assert record["document_id"] == "inv_001"
    assert record["exit_code"] == int(ExitCode.INVALID_PDF)
    # No artifacts produced.
    assert not (folder / "preprocess_output.json").exists()


def test_warm_corpus_document_path_file_reports_output_path_not_usable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Existing non-directory corpus entries mirror cold output-path handling."""
    docs_file = tmp_path / "corpus.txt"
    path = tmp_path / "inv_002_easy"
    path.write_text("not a directory", encoding="utf-8")
    docs_file.write_text(path.name + "\n", encoding="utf-8")

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])

    from ledgerlinc_ocr.pipeline.exit_codes import ExitCode
    assert code == int(ExitCode.OUTPUT_PATH_NOT_USABLE)
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    record = summary["per_document"][0]
    assert record["document_id"] == "inv_002"
    assert record["exit_code"] == int(ExitCode.OUTPUT_PATH_NOT_USABLE)
    assert "not a directory" in record["message"]


def test_warm_corpus_unwritable_folder_reports_output_path_not_usable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
):
    """Warm-corpus validates destination writability before stage execution."""
    from ledgerlinc_ocr.pipeline import corpus_run as corpus_run_mod
    from ledgerlinc_ocr.pipeline.exit_codes import ExitCode

    docs_file, _folder = _build_corpus(tmp_path, with_pdf=True)
    monkeypatch.setattr(corpus_run_mod.os, "access", lambda _p, _mode: False)

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])

    assert code == int(ExitCode.OUTPUT_PATH_NOT_USABLE)
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    record = summary["per_document"][0]
    assert record["exit_code"] == int(ExitCode.OUTPUT_PATH_NOT_USABLE)
    assert "not writable" in record["message"]
