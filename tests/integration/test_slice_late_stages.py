"""US2 Acceptance Scenario 2: routing+final_payload slice over a folder
with valid upstream artifacts. Earlier artifacts MUST NOT be rewritten.

Spec User Story 2 Acceptance Scenario 2; FR-009 / FR-011.
"""
from __future__ import annotations

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
def folder_with_upstream_artifacts(tmp_path: Path) -> Path:
    """Build a folder containing source.pdf + preprocess + extract artifacts."""
    folder = tmp_path / "inv_002_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    # Drop the two downstream artifacts so the slice re-creates them.
    (folder / "routing_decision.json").unlink()
    (folder / "final_structured_payload.json").unlink()
    return folder


def test_routing_to_final_payload_slice_leaves_upstream_untouched(
    folder_with_upstream_artifacts: Path,
):
    folder = folder_with_upstream_artifacts
    preprocess_before = (folder / "preprocess_output.json").read_bytes()
    extract_before = (folder / "edge_extraction_output.json").read_bytes()

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "routing",
        "--stop-after", "final_payload",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    # Slice outputs created.
    assert (folder / "routing_decision.json").exists()
    assert (folder / "final_structured_payload.json").exists()
    # Upstream artifacts byte-identical.
    assert (folder / "preprocess_output.json").read_bytes() == preprocess_before
    assert (folder / "edge_extraction_output.json").read_bytes() == extract_before


def test_final_payload_only_slice(folder_with_upstream_artifacts: Path):
    """--start-at final_payload --stop-after final_payload runs only assembler."""
    folder = folder_with_upstream_artifacts
    # Stage routing_decision so final_payload has its prerequisite.
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "routing",
        "--stop-after", "routing",
        "--routing-profile", "stub",
    ])
    assert code == 0
    routing_before = (folder / "routing_decision.json").read_bytes()

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "final_payload",
        "--stop-after", "final_payload",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    assert (folder / "final_structured_payload.json").exists()
    # routing_decision unchanged.
    assert (folder / "routing_decision.json").read_bytes() == routing_before
