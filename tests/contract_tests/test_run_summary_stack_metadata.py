"""US5 Acceptance Scenario 2 / SC-008: run summary records stack_preset
verbatim and resolved_profiles.extract is ensemble@workstation under
--stack-preset cloud-workstation, even though the deferred adapter is
never dispatched.

Spec FR-022; design.md CHK049.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def _stage_preprocessed_corpus(tmp_path: Path, n: int = 1) -> tuple[Path, list[Path]]:
    from dartwing_ocr.pipeline.cli import main

    docs_file = tmp_path / "corpus.txt"
    folders: list[Path] = []
    for i in range(n):
        folder = tmp_path / f"inv_{i + 1:03d}_easy"
        folder.mkdir()
        (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
        # Stage all four artifacts via stub so we have a clean slice
        # starting point for the routing-onwards test below.
        code = main([
            "run",
            "--document-folder", str(folder),
            "--preprocess-profile", "stub",
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
        ])
        assert code == 0
        # Drop the slice we plan to re-run.
        (folder / "routing_decision.json").unlink()
        (folder / "final_structured_payload.json").unlink()
        folders.append(folder)
    docs_file.write_text(
        "\n".join(f.name for f in folders) + "\n",
        encoding="utf-8",
    )
    return docs_file, folders


def test_cloud_workstation_run_summary_records_preset_and_resolved_profiles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A successful cloud-workstation slice that EXCLUDES extract still
    records stack_preset and resolved_profiles.extract verbatim.
    """
    from dartwing_ocr.pipeline.cli import main

    docs_file, _ = _stage_preprocessed_corpus(tmp_path, n=1)
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--stack-preset", "cloud-workstation",
        "--start-at", "routing",
        "--stop-after", "routing",
        "--routing-profile", "stub",
    ])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])

    assert summary["kind"] == "run_summary"
    assert summary["stack_preset"] == "cloud-workstation"
    # Resolved profiles include the preset's expansion verbatim, even for
    # stages that were not in the slice (the resolver runs end-to-end).
    assert summary["resolved_profiles"]["extract"] == "ensemble@workstation"
    assert summary["resolved_profiles"]["preprocess"] == "ppstructurev3@cpu"
    assert summary["resolved_profiles"]["routing"] == "stub"  # explicit override
    assert summary["resolved_profiles"]["final_payload"] == "assembler@cpu"
    assert summary["execution_slice"] == {
        "start_at": "routing",
        "stop_after": "routing",
    }
