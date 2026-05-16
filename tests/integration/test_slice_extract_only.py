"""US2 / Acceptance Scenario 1: extract-only slice with valid prerequisite.

Spec User Story 2 Acceptance Scenario 1; FR-009 / FR-010.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.pipeline.cli import main


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


@pytest.fixture
def folder_with_preprocess_artifact(tmp_path: Path) -> Path:
    """Stage a per-document folder containing a valid preprocess_output.json
    (produced by a prior stub run) so an extract-only slice has its prereq.
    """
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    # Run the full stub pipeline once to produce all four artifacts; we'll
    # then delete the three downstream artifacts so the extract-only
    # rerun has only its prerequisite present.
    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    for name in ("edge_extraction_output.json", "routing_decision.json", "final_structured_payload.json"):
        (folder / name).unlink()
    return folder


def test_extract_only_slice_writes_only_extract_artifact(folder_with_preprocess_artifact: Path):
    """Acceptance Scenario 1: --start-at extract --stop-after extract rewrites only edge_extraction_output.json."""
    folder = folder_with_preprocess_artifact
    preprocess_before = (folder / "preprocess_output.json").read_bytes()

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "extract",
        "--stop-after", "extract",
        "--extract-profile", "stub",
    ])
    assert code == 0

    # Only the slice output exists post-run.
    assert (folder / "edge_extraction_output.json").exists()
    assert not (folder / "routing_decision.json").exists()
    assert not (folder / "final_structured_payload.json").exists()
    # Prerequisite artifact was NOT rewritten.
    assert (folder / "preprocess_output.json").read_bytes() == preprocess_before


def test_extract_only_slice_reads_existing_preprocess(folder_with_preprocess_artifact: Path):
    """The runner treats the existing preprocess_output.json as input, not output."""
    folder = folder_with_preprocess_artifact
    preprocess = json.loads((folder / "preprocess_output.json").read_text())
    document_id = preprocess["document_id"]

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "extract",
        "--stop-after", "extract",
        "--extract-profile", "stub",
    ])
    assert code == 0
    extraction = json.loads(
        (folder / "edge_extraction_output.json").read_text()
    )
    assert extraction["document_id"] == document_id
