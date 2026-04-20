"""US3 AC#5 — every page fails at PaddleOCR layer.

Expected: artifact still schema-valid, `paddleocr_vl.status == "failure"`,
warning surfaces the source-level failure.
"""

from __future__ import annotations

import json
import shutil


def test_ac5_paddleocr_total_failure(tmp_path, us3_fixtures, monkeypatch):
    from ledgerlinc_ocr.preprocessing import ocr, pipeline

    folder = tmp_path / "inv_030"
    folder.mkdir()
    shutil.copy(us3_fixtures["partial"], folder / "source.pdf")

    def always_raise(*args, **kwargs):
        raise RuntimeError("simulated PaddleOCR total failure")

    monkeypatch.setattr(ocr, "run_ocr_lines", always_raise)
    monkeypatch.setattr(ocr, "run_layout", always_raise)

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
