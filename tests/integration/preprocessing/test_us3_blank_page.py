"""US3 AC#2 — blank page is silent success (no warning, valid artifact)."""

from __future__ import annotations

import json
import shutil


def test_ac2_blank_page_no_warning(tmp_path, us3_fixtures):
    from dartwing_ocr.preprocessing import pipeline

    folder = tmp_path / "inv_031"
    folder.mkdir()
    shutil.copy(us3_fixtures["blank"], folder / "source.pdf")

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    assert art["page_count"] == 2
    page1 = next(p for p in art["pages"] if p["page_number"] == 1)
    # Blank page: OCR and layout succeed but return nothing.
    assert page1["blocks"] == []
    assert page1["raw_ocr_lines"] == []

    # No failure warnings should mention page 1.
    for w in art["warnings"]:
        assert not (w.startswith("page 1:") and "failed" in w), w

    # paddleocr_vl remains "success" because page 2 produced output.
    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "success"
