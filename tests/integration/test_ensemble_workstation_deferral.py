"""US5 Acceptance Scenarios 1 + 3: ensemble@workstation deferral.

Spec FR-022A; Research R-013. Design checklist CHK040-CHK041.
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


def test_stack_preset_cloud_workstation_fails_fast_with_named_deferral(
    folder: Path, capsys: pytest.CaptureFixture[str]
):
    """Acceptance Scenario 1 / 3: --stack-preset cloud-workstation expands
    to ensemble@workstation and fails fast with a named missing-endpoint
    error before any artifact write.
    """
    code = main([
        "run",
        "--document-folder", str(folder),
        "--stack-preset", "cloud-workstation",
        "--overwrite",
    ])
    assert code == 10  # USAGE_ERROR per R-013
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "USAGE_ERROR"
    assert "ensemble@workstation" in rec["message"]
    assert "FR-034 step 4" in rec["message"]
    # No artifacts written.
    for name in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
    ):
        assert not (folder / name).exists()


def test_explicit_extract_profile_ensemble_workstation_fails_fast(
    folder: Path, capsys: pytest.CaptureFixture[str]
):
    """Even without the preset, explicit --extract-profile ensemble@workstation
    fails fast inside the slice.
    """
    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "stub",
        "--extract-profile", "ensemble@workstation",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 10
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert "ensemble@workstation" in rec["message"]
