"""US3 AC#4 — per-step failure boundary.

Historical AC#4 distinguished "OCR failed / layout succeeded" from "layout
failed / OCR succeeded". Under the V3 migration (FR-007) layout and OCR come
from the same `PPStructureV3.predict(...)` call, so the per-step decomposition
no longer exists at the engine layer. The V3-era analogues are:

- `run_page` catches its own `engine.predict` exceptions and returns
  `([], [], [], [<layout extraction failed>])`, producing an empty-but-valid
  artifact.
- The FR-003 and FR-019 silent-empty paths cover the "lines but no blocks"
  and "blocks but no lines" asymmetries directly; those scenarios have
  dedicated integration tests (`test_silent_empty_layout.py`,
  `test_silent_empty_ocr.py`).

This test consolidates AC#4 into a single check of the V3 engine-crash path.
"""

from __future__ import annotations

import json
import shutil


def _staged_folder(tmp_path, us3_fixtures, name):
    folder = tmp_path / name
    folder.mkdir()
    shutil.copy(us3_fixtures["partial"], folder / "source.pdf")
    return folder


def test_ac4_engine_predict_crash_produces_empty_valid_artifact(
    tmp_path, us3_fixtures, monkeypatch,
):
    from dartwing_ocr.preprocessing import ocr, pipeline

    folder = _staged_folder(tmp_path, us3_fixtures, "inv_030")

    # Mirror `run_page`'s internal try/except contract: a per-page engine
    # crash surfaces as `([], [], [], [layout extraction failed warning])`.
    def fake_engine_crash(img, page, w, h):
        return [], [], [], [
            f"page {page}: layout extraction failed: "
            f"RuntimeError: simulated engine crash"
        ]

    monkeypatch.setattr(ocr, "run_page", fake_engine_crash)

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    for page in art["pages"]:
        assert page["blocks"] == [], page
        assert page["raw_ocr_lines"] == [], page
    assert any("layout extraction failed" in w for w in art["warnings"]), art["warnings"]
    # All pages empty → aggregate "all pages failed" warning MUST fire.
    assert any(
        "paddleocr_vl" in w and "failure" in w for w in art["warnings"]
    ), art["warnings"]
    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "failure"
