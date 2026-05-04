"""US3 Acceptance Scenario 5: invalid lane combos rejected at argument validation.

Spec FR-008 / FR-018; SC-005; Research R-002. Design checklist CHK010.
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


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    f = tmp_path / "inv_001_easy"
    f.mkdir()
    (f / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    return f


@pytest.mark.parametrize(
    "stage_flag,bad_value",
    [
        ("--preprocess-profile", "stub@cpu"),
        ("--preprocess-profile", "stub@gpu"),
        ("--preprocess-profile", "ppstructurev3@gpu"),
        ("--preprocess-profile", "edge-ocr@cpu"),
        ("--extract-profile", "stub@cpu"),
        ("--extract-profile", "ensemble@cloud"),
        ("--extract-profile", "ollama@workstation"),
        ("--extract-profile", "gemma"),
        ("--extract-profile", "gemma@cpu"),
        ("--routing-profile", "rules@gpu"),
        ("--routing-profile", "rules@jetson"),
        ("--final-payload-profile", "assembler@gpu"),
    ],
)
def test_invalid_profile_rejected_at_argument_validation(
    folder: Path, capsys: pytest.CaptureFixture[str], stage_flag: str, bad_value: str
):
    """SC-005: invalid stage profile -> USAGE_ERROR before any artifact write."""
    code = main([
        "run",
        "--document-folder", str(folder),
        stage_flag, bad_value,
    ])
    assert code == 10
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "USAGE_ERROR"
    assert rec["stage"] == "arguments"
    # No artifacts written.
    for name in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
    ):
        assert not (folder / name).exists()


def test_unknown_stack_preset_rejected(folder: Path, capsys: pytest.CaptureFixture[str]):
    code = main([
        "run",
        "--document-folder", str(folder),
        "--stack-preset", "unknown-preset",
    ])
    assert code == 10


def test_start_after_stop_rejected(folder: Path, capsys: pytest.CaptureFixture[str]):
    code = main([
        "run",
        "--document-folder", str(folder),
        "--start-at", "extract",
        "--stop-after", "preprocess",
    ])
    assert code == 10
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert "must not be later than" in rec["message"]
