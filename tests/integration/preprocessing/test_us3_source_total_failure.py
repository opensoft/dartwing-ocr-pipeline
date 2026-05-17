"""US3 AC#5 — every page fails at PaddleOCR layer.

Expected: artifact still schema-valid, `paddleocr_vl.status == "failure"`,
warning surfaces the source-level failure.
"""

from __future__ import annotations

import json
import shutil


def test_ac5_paddleocr_total_failure(tmp_path, us3_fixtures, monkeypatch):
    from dartwing_ocr.preprocessing import ocr, pipeline

    folder = tmp_path / "inv_030"
    folder.mkdir()
    shutil.copy(us3_fixtures["partial"], folder / "source.pdf")

    # V3 migration (FR-007): the pair `run_ocr_lines`/`run_layout` is retired;
    # all per-page inference flows through `run_page`. `run_page` catches its
    # own per-page runtime exceptions and returns `([], [], [], [warning])`,
    # so the stub mirrors that contract directly.
    def fail_at_engine_layer(image, page_number, width, height):
        warning = (
            f"page {page_number}: layout extraction failed: "
            f"RuntimeError: simulated PaddleOCR total failure"
        )
        return [], [], [], [warning]

    monkeypatch.setattr(ocr, "run_page", fail_at_engine_layer)

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "failure"
    # Every page must be schema-valid with empty content.
    for page in art["pages"]:
        assert page["blocks"] == []
        assert page["raw_ocr_lines"] == []
    # A document-level warning must surface the source failure.
    assert any("paddleocr_vl" in w and "failure" in w for w in art["warnings"]), (
        art["warnings"]
    )
