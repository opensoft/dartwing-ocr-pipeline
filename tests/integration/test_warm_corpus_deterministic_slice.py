"""US6 Edge Case: warm-corpus run with a deterministic-only slice MUST NOT
initialize any live preprocessing profile.

Spec Edge Cases (warm-corpus deterministic-only-stages bullet); design.md CHK054.
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


def _stage_corpus_with_upstream_artifacts(tmp_path: Path, n: int = 2) -> tuple[Path, list[Path]]:
    """Create N folders that already have preprocess + extract artifacts so a
    routing/final_payload-only slice has its prerequisites without invoking
    the preprocess/extract stages.
    """
    docs_file = tmp_path / "corpus.txt"
    folders: list[Path] = []
    for i in range(n):
        folder = tmp_path / f"inv_{i + 1:03d}_easy"
        folder.mkdir()
        (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
        # Run a full stub pipeline once to produce all four artifacts.
        code = main([
            "run",
            "--document-folder", str(folder),
            "--preprocess-profile", "stub",
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
        ])
        assert code == 0
        # Drop the slice's outputs (routing + final_payload) so the warm
        # run can re-create them.
        (folder / "routing_decision.json").unlink()
        (folder / "final_structured_payload.json").unlink()
        folders.append(folder)
    docs_file.write_text(
        "\n".join(f.name for f in folders) + "\n",
        encoding="utf-8",
    )
    return docs_file, folders


def test_deterministic_only_slice_does_not_warm_preprocess(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    docs_file, _ = _stage_corpus_with_upstream_artifacts(tmp_path, n=2)
    code = main([
        "run",
        "--documents-file", str(docs_file),
        "--start-at", "routing",
        "--stop-after", "final_payload",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
    ])
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])
    # No live preprocess profile in the slice -> no init timing.
    assert summary["profile_initialization_seconds"] == {}
    assert summary["execution_slice"] == {
        "start_at": "routing",
        "stop_after": "final_payload",
    }
