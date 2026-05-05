"""US6 / Quickstart Section 3b: warm corpus stub-only smoke test.

Spec FR-023 / FR-027; Research R-009.

Verifies that --documents-file mode runs end-to-end with all-stub
profiles, emits per-document success records on stdout, and emits the
end-of-run kind:"run_summary" object as the LAST stdout line.
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


def _stage_three_folders(tmp_path: Path) -> tuple[Path, list[Path]]:
    docs_file = tmp_path / "corpus.txt"
    folders: list[Path] = []
    for i in range(3):
        folder = tmp_path / f"inv_{i + 1:03d}_easy"
        folder.mkdir()
        (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
        folders.append(folder)
    docs_file.write_text(
        "\n".join(f.name for f in folders) + "\n",
        encoding="utf-8",
    )
    return docs_file, folders


def test_warm_corpus_stub_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    docs_file, folders = _stage_three_folders(tmp_path)
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0

    out = capsys.readouterr().out.strip().splitlines()
    # 3 per-document records + 1 run-summary = 4 lines.
    assert len(out) == 4
    summary = json.loads(out[-1])
    assert summary["kind"] == "run_summary"
    assert summary["schema_version"] == "0.1.0"
    assert summary["documents_total"] == 3
    assert summary["documents_succeeded"] == 3
    assert summary["documents_failed"] == 0
    # No live preprocess profile -> no init timings recorded.
    assert summary["profile_initialization_seconds"] == {}
    # All-stub run -> stack_preset is null and resolved_profiles all stub.
    assert summary["stack_preset"] is None
    assert summary["resolved_profiles"] == {
        "preprocess": "stub",
        "extract": "stub",
        "routing": "stub",
        "final_payload": "stub",
    }
    # Per-document records list contains 3 success entries in order.
    per_doc = summary["per_document"]
    assert len(per_doc) == 3
    for entry, folder in zip(per_doc, folders):
        assert entry["status"] == "success"
        # Folder echoes the raw token from --documents-file, not the
        # resolved absolute path (Copilot review item 3).
        assert entry["folder"] == folder.name
        assert entry["document_id"] == folder.name
    # Each document's folder has all four canonical artifacts.
    for folder in folders:
        for name in (
            "preprocess_output.json",
            "edge_extraction_output.json",
            "routing_decision.json",
            "final_structured_payload.json",
        ):
            assert (folder / name).exists()


def test_warm_corpus_per_document_records_match_002_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """R-009: per-document stdout records keep the existing 002 shape (no kind field)."""
    docs_file, _ = _stage_three_folders(tmp_path)
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    # First three lines are per-document records, no `kind` field.
    for line in out[:3]:
        rec = json.loads(line)
        assert "kind" not in rec
        assert "document_id" in rec
        assert "decision" in rec
        assert "manual_review_required" in rec
        assert "review_reason" in rec
        assert "artifacts" in rec
