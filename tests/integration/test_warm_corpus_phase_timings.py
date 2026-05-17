"""Copilot review item 4: warm-corpus run summary emits per-phase timings
(infer/compute + write) per FR-027 / R-009, not just total + write.
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


def test_warm_corpus_per_document_phase_timings_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Per FR-027: every executed stage records a compute-or-infer phase
    plus a write phase. ``total_seconds`` is also present.
    """
    docs_file = tmp_path / "corpus.txt"
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
    docs_file.write_text("inv_001_easy\n", encoding="utf-8")

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
    summary = json.loads(out[-1])
    stages = summary["per_document"][0]["stages"]

    # Expected per-stage phase keys (data-model.md "Per-stage phase keys"):
    # preprocess -> infer + write; extract -> infer + write;
    # routing -> compute + write; final_payload -> compute + write.
    expected = {
        "preprocess": {"infer_seconds", "write_seconds", "total_seconds"},
        "extract": {"infer_seconds", "write_seconds", "total_seconds"},
        "routing": {"compute_seconds", "write_seconds", "total_seconds"},
        "final_payload": {"compute_seconds", "write_seconds", "total_seconds"},
    }
    for stage_name, required in expected.items():
        assert stage_name in stages, f"missing stage {stage_name}"
        observed = set(stages[stage_name].keys())
        assert required <= observed, (
            f"{stage_name}: missing phases {required - observed} "
            f"(observed: {observed})"
        )
        for key in required:
            assert isinstance(stages[stage_name][key], (int, float)), (
                f"{stage_name}.{key} must be a number, got "
                f"{type(stages[stage_name][key])}"
            )
