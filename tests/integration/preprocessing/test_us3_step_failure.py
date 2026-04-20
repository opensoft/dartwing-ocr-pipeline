"""US3 AC#4 — per-step failure boundary.

When OCR fails but layout succeeds: keep `blocks` (text possibly empty),
`raw_ocr_lines == []`, warning names the step. Symmetric when layout fails.
"""

from __future__ import annotations

import json
import shutil


def _staged_folder(tmp_path, us3_fixtures, name):
    folder = tmp_path / name
    folder.mkdir()
    shutil.copy(us3_fixtures["partial"], folder / "source.pdf")
    return folder


def test_ac4_ocr_failed_layout_succeeded(tmp_path, us3_fixtures, monkeypatch):
    from ledgerlinc_ocr.preprocessing import ocr, pipeline

    folder = _staged_folder(tmp_path, us3_fixtures, "inv_030")

    def fake_ocr(img, page, w, h):
        raise RuntimeError("simulated OCR detector crash")

    monkeypatch.setattr(ocr, "run_ocr_lines", fake_ocr)

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    for page in art["pages"]:
        assert page["raw_ocr_lines"] == [], page
    assert any("OCR failed" in w for w in art["warnings"]), art["warnings"]
    # Layout succeeded → some page should have at least structural blocks
    # even if their `text` is empty. (PPStructure on text pages yields text blocks.)
    assert any(len(p["blocks"]) > 0 for p in art["pages"]), (
        "layout should still populate blocks"
    )


def test_ac4_layout_failed_ocr_succeeded(tmp_path, us3_fixtures, monkeypatch):
    from ledgerlinc_ocr.preprocessing import ocr, pipeline

    folder = _staged_folder(tmp_path, us3_fixtures, "inv_030")

    def fake_layout(img, page, w, h):
        raise RuntimeError("simulated layout crash")

    monkeypatch.setattr(ocr, "run_layout", fake_layout)

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    for page in art["pages"]:
        assert page["blocks"] == [], page
    assert any("layout extraction failed" in w for w in art["warnings"]), art["warnings"]
    assert any(len(p["raw_ocr_lines"]) > 0 for p in art["pages"]), (
        "OCR should still populate raw_ocr_lines"
    )
