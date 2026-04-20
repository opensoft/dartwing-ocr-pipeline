"""US3 AC#1 — one unreadable page among readable pages.

Rasterization failure on page 2 is simulated via monkeypatch: pypdfium2 is
robust enough that a Pillow-written PDF cannot easily be corrupted page-wise
without breaking the whole document, so the synthetic failure is injected by
wrapping `page.render` to raise for page_number == 2. The fixture PDF itself
is structurally valid (3 clean pages) — the behavior under test is the
per-page raster failure boundary.
"""

from __future__ import annotations

import json
import shutil

import pytest


def test_ac1_one_unreadable_page(tmp_path, us3_fixtures, monkeypatch):
    from ledgerlinc_ocr.preprocessing import pipeline, rasterize

    folder = tmp_path / "inv_030"
    folder.mkdir()
    shutil.copy(us3_fixtures["partial"], folder / "source.pdf")

    real_rasterize = rasterize.rasterize_pdf

    def patched(pdf_path, dpi):
        rasters = real_rasterize(pdf_path, dpi=dpi)
        out: list = []
        for r in rasters:
            if isinstance(r, rasterize.PageRaster) and r.page_number == 2:
                fb_w = max(1, r.width)
                fb_h = max(1, r.height)
                out.append(
                    rasterize.PageRasterFailure(
                        page_number=2,
                        width=fb_w,
                        height=fb_h,
                        rotation_detected=0,
                        error="RuntimeError: simulated page-2 rasterization failure",
                    )
                )
            else:
                out.append(r)
        return out

    monkeypatch.setattr(rasterize, "rasterize_pdf", patched)

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    assert art["page_count"] == 3
    page2 = next(p for p in art["pages"] if p["page_number"] == 2)
    assert page2["blocks"] == []
    assert page2["raw_ocr_lines"] == []
    assert page2["width"] >= 1
    assert page2["height"] >= 1
    assert page2["rotation_detected"] == 0

    # Pages 1 and 3 must still have real output.
    other = [p for p in art["pages"] if p["page_number"] != 2]
    assert any(p["blocks"] or p["raw_ocr_lines"] for p in other), (
        "pages 1 and 3 should still have OCR output"
    )

    # Warning must name the page and cite rasterization.
    assert any(
        w.startswith("page 2:") and "rasterization failed" in w
        for w in art["warnings"]
    ), art["warnings"]
