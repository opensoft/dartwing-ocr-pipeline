"""US3 Acceptance Scenarios 3-4: ollama@jetson and edge-ocr@jetson are
recognized at argument validation but their live execution is deferred
to FR-034 step 4.

Spec User Story 3 Acceptance Scenarios 3-4; FR-035; Research R-013 / R-014.
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
def folder(tmp_path: Path) -> Path:
    f = tmp_path / "inv_001_easy"
    f.mkdir()
    (f / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return f


def test_ollama_jetson_recognized_at_validation_but_fails_at_dispatch(
    folder: Path, capsys: pytest.CaptureFixture[str]
):
    """Acceptance Scenario 4: --extract-profile ollama@jetson is accepted
    by argparse, then the adapter dispatch raises DeferredImplementationError.
    """
    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "stub",
        "--extract-profile", "ollama@jetson",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 10  # USAGE_ERROR (R-013)
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "USAGE_ERROR"
    # Stage failure record names "extraction" (the canonical 002 stage
    # name; the deferred profile is reported in the message).
    assert "ollama@jetson" in rec["message"]
    assert "FR-034 step 4" in rec["message"]
    # FR-022A: deferred-profile fail-fast happens BEFORE any artifact write.
    assert not (folder / "preprocess_output.json").exists()
    assert not (folder / "edge_extraction_output.json").exists()


def test_edge_ocr_jetson_recognized_at_validation_but_fails_at_dispatch(
    folder: Path, capsys: pytest.CaptureFixture[str]
):
    """Acceptance Scenario 3: --preprocess-profile edge-ocr@jetson is
    accepted by argparse, then the adapter dispatch raises
    DeferredImplementationError on first use.
    """
    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "edge-ocr@jetson",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 10
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert "edge-ocr@jetson" in rec["message"]
    assert "FR-034 step 4" in rec["message"]
    # No artifacts written.
    assert not (folder / "preprocess_output.json").exists()


def test_stack_preset_edge_fast_resolves_to_deferred_profiles(folder: Path, capsys: pytest.CaptureFixture[str]):
    """SC-007 (deferred): --stack-preset edge-fast expands cleanly but its
    live execution is deferred end-to-end.
    """
    code = main([
        "run",
        "--document-folder", str(folder),
        "--stack-preset", "edge-fast",
        "--overwrite",
    ])
    assert code == 10
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    # The first stage in the preset is preprocess=edge-ocr@jetson; that's
    # what the deferred-implementation error names.
    assert "edge-ocr@jetson" in rec["message"]
