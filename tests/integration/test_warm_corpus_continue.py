"""US6 / Acceptance Scenario 3: continue-through-failures default.

Spec FR-028; Research R-008. Verifies:
  - Default failure policy in warm-corpus mode is `continue`.
  - One bad document is recorded but the run continues.
  - Run summary reflects the mixed outcome.
  - Process exit code is the highest-severity per-document failure code.
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


def test_continue_through_failures_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Mixed corpus: 2 valid folders + 1 invalid (bad folder name)."""
    docs_file = tmp_path / "corpus.txt"
    valid_a = tmp_path / "inv_001_easy"
    valid_b = tmp_path / "inv_002_easy"
    invalid = tmp_path / "bad_name_folder"
    for f in (valid_a, valid_b, invalid):
        f.mkdir()
        (f / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text(
        "\n".join([valid_a.name, invalid.name, valid_b.name]) + "\n",
        encoding="utf-8",
    )

    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    # Aggregate exit code is non-zero because one document failed; specifically
    # the invalid document yields USAGE_ERROR (10) at corpus_validation.
    assert code != 0
    captured = capsys.readouterr()
    out_lines = captured.out.strip().splitlines()
    err_lines = captured.err.strip().splitlines()

    # Two success records on stdout + one run summary line.
    assert len(out_lines) == 3
    summary = json.loads(out_lines[-1])
    assert summary["documents_total"] == 3
    assert summary["documents_succeeded"] == 2
    assert summary["documents_failed"] == 1
    assert summary["on_failure"] == "continue"

    # Per-document records preserve list order from documents-file.
    per_doc = summary["per_document"]
    assert len(per_doc) == 3
    assert per_doc[0]["status"] == "success"
    assert per_doc[1]["status"] == "failure"
    assert per_doc[2]["status"] == "success"
    assert per_doc[1]["document_id"] == invalid.name

    # The bad document's failure record on stderr names the failed stage.
    assert err_lines, "expected at least one structured failure record on stderr"
    failure_records = [json.loads(line) for line in err_lines]
    bad_records = [
        r for r in failure_records
        if r.get("stage") in ("corpus_validation", "arguments")
    ]
    assert bad_records


def test_explicit_continue_equivalent_to_default(tmp_path: Path):
    docs_file = tmp_path / "corpus.txt"
    folder = tmp_path / "inv_010_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text(folder.name + "\n", encoding="utf-8")
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--on-failure", "continue",
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
