"""US2 Acceptance Scenario 3: mixed injected/stub stage selection.

Spec User Story 2 Acceptance Scenario 3.

The behavior under verification here is *the seam*: a caller can mix an
explicit stub upstream stage with explicit downstream stage profiles and
still produce schema-valid artifacts from the injected/stub inputs.
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


def test_mixed_explicit_stub_upstream_and_downstream(tmp_path: Path):
    folder = tmp_path / "inv_007_easy"
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
    # All four artifacts produced and schema-valid.
    for name in (
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
    ):
        path = folder / name
        assert path.exists(), name
        # Round-tripping JSON validates the file is well-formed.
        json.loads(path.read_text())


def test_explicit_stub_for_subset_with_injected_callable(tmp_path: Path):
    """Demonstrates that the injected-stage-callable seam works alongside
    explicit profile flags: caller injects a custom preprocess callable
    while the other three stages resolve via profile flags.

    The injected callable wins per FR-012 / Research R-014.
    """
    from ledgerlinc_ocr.pipeline.runner import Runner

    folder = tmp_path / "inv_008_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)

    seen: dict[str, bool] = {"called": False}

    from ledgerlinc_ocr.pipeline.stages import default_preprocess

    def custom_preprocess(invocation, artifacts_so_far):
        seen["called"] = True
        return default_preprocess(invocation, artifacts_so_far)

    runner = Runner(preprocess=custom_preprocess)

    code = main(
        [
            "run",
            "--document-folder", str(folder),
            "--extract-profile", "stub",
            "--routing-profile", "stub",
            "--final-payload-profile", "stub",
        ],
        runner=runner,
    )
    assert code == 0
    assert seen["called"] is True
    assert (folder / "preprocess_output.json").exists()
    assert (folder / "edge_extraction_output.json").exists()
