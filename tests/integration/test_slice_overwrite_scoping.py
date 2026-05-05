"""US2 Acceptance Scenario 5: overwrite guard scopes to slice outputs only.

Spec User Story 2 Acceptance Scenario 5; FR-011; Research R-006; design.md CHK014.
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


def _stage_full_artifacts(tmp_path: Path, name: str = "inv_004_easy") -> Path:
    folder = tmp_path / name
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
    return folder


def test_stop_after_preprocess_with_downstream_artifacts_present_succeeds_no_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Positive overwrite scoping (R-006): downstream artifacts that exist on
    disk MUST NOT trigger OUTPUT_IN_USE for a slice that does not write them.

    Setup: full pipeline already ran (all four artifacts present). Caller
    runs --stop-after preprocess WITHOUT --overwrite. Expectation: only
    preprocess_output.json is in the slice's output set, so it would
    block; we delete it first to give the slice a clean output target.
    """
    folder = _stage_full_artifacts(tmp_path, "inv_004_easy")
    # Remove only the slice's output (preprocess_output.json) so the
    # slice can write it cleanly. The three downstream artifacts remain.
    (folder / "preprocess_output.json").unlink()
    extract_before = (folder / "edge_extraction_output.json").read_bytes()
    routing_before = (folder / "routing_decision.json").read_bytes()
    final_before = (folder / "final_structured_payload.json").read_bytes()

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "preprocess",
        "--stop-after", "preprocess",
        "--preprocess-profile", "stub",
    ])
    assert code == 0  # downstream artifacts do NOT trigger OUTPUT_IN_USE
    # Downstream artifacts are unchanged.
    assert (folder / "edge_extraction_output.json").read_bytes() == extract_before
    assert (folder / "routing_decision.json").read_bytes() == routing_before
    assert (folder / "final_structured_payload.json").read_bytes() == final_before
    record = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert record["decision"] is None
    assert record["manual_review_required"] is False
    assert record["review_reason"] is None


def test_in_slice_artifact_present_blocks_without_overwrite(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Negative overwrite scoping (R-006): if the slice's own output is
    already on disk and --overwrite is not passed, the run fails with
    OUTPUT_IN_USE (exit 13).
    """
    folder = _stage_full_artifacts(tmp_path, "inv_005_easy")
    # All four artifacts present. Run preprocess slice WITHOUT --overwrite
    # -- preprocess_output.json is the slice's output, so it must block.
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "preprocess",
        "--stop-after", "preprocess",
        "--preprocess-profile", "stub",
    ])
    assert code == 13
    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["exit_code_name"] == "OUTPUT_IN_USE"
    assert "preprocess_output.json" in record["message"]


def test_in_slice_directory_artifact_path_reports_unusable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    folder = tmp_path / "inv_007_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    (folder / "preprocess_output.json").mkdir()

    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "preprocess",
        "--stop-after", "preprocess",
        "--preprocess-profile", "stub",
        "--overwrite",
    ])

    assert code == 14
    record = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert record["exit_code_name"] == "OUTPUT_PATH_NOT_USABLE"
    assert "preprocess_output.json" in record["message"]


def test_overwrite_replaces_only_slice_outputs(tmp_path: Path):
    """With --overwrite, the slice replaces only its output artifacts;
    out-of-slice artifacts MUST remain untouched.
    """
    folder = _stage_full_artifacts(tmp_path, "inv_006_easy")
    extract_before = (folder / "edge_extraction_output.json").read_bytes()
    routing_before = (folder / "routing_decision.json").read_bytes()
    final_before = (folder / "final_structured_payload.json").read_bytes()

    # Run preprocess-only slice WITH --overwrite.
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "preprocess",
        "--stop-after", "preprocess",
        "--preprocess-profile", "stub",
        "--overwrite",
    ])
    assert code == 0
    # Out-of-slice artifacts unchanged.
    assert (folder / "edge_extraction_output.json").read_bytes() == extract_before
    assert (folder / "routing_decision.json").read_bytes() == routing_before
    assert (folder / "final_structured_payload.json").read_bytes() == final_before
