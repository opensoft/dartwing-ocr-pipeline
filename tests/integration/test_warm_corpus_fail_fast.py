"""US6: --on-failure fail-fast aborts after the first failed document.

Spec FR-028; Research R-008.
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


def test_fail_fast_stops_after_first_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    docs_file = tmp_path / "corpus.txt"
    bad = tmp_path / "no_pdf_here"
    bad.mkdir()
    # Note: NO source.pdf in `bad` -- runner will fail with INPUT_NOT_FOUND.
    later = tmp_path / "inv_999_easy"
    later.mkdir()
    (later / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text(
        "\n".join([bad.name, later.name]) + "\n",
        encoding="utf-8",
    )

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--on-failure", "fail-fast",
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code != 0
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])
    # documents_total reflects the input file's length; per_document and
    # documents_succeeded/_failed reflect what was actually attempted.
    assert summary["documents_total"] == 2
    assert summary["documents_failed"] == 1
    assert summary["documents_succeeded"] == 0
    # The second document was skipped by fail-fast and should NOT appear
    # in per_document.
    per_doc = summary["per_document"]
    assert len(per_doc) == 1
    assert per_doc[0]["status"] == "failure"
    assert summary["on_failure"] == "fail-fast"
