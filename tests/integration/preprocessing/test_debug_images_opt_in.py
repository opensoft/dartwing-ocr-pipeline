"""FR-022 / R-015: debug `page_*.png` emission is opt-in via --write-page-images.

Default behavior: no PNGs written. Flag present: one PNG per `PageRaster` page.
PNGs are explicitly OUTSIDE FR-004's byte-identical determinism guarantee, so
this test does NOT assert on PNG content or sha256 — only on presence/absence.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from ledgerlinc_ocr.preprocessing import ocr, pipeline, rasterize
from ledgerlinc_ocr.preprocessing.rasterize import PageRaster


def _fake_page(n: int) -> PageRaster:
    return PageRaster(
        page_number=n,
        width=100,
        height=100,
        rotation_detected=0,
        rotation_original=0,
        rotation_snapped=False,
        image=Image.new("RGB", (100, 100), "white"),
    )


def _stub_document(tmp_path, monkeypatch, page_count: int = 2) -> Path:
    folder = tmp_path / "inv_099"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%stub\n")

    def _fake_rasterize(pdf_path, dpi):
        # Yield pages one at a time — matches the FR-005a streaming contract.
        for n in range(1, page_count + 1):
            yield _fake_page(n)

    monkeypatch.setattr(rasterize, "rasterize_pdf", _fake_rasterize)
    monkeypatch.setattr(ocr, "run_page", lambda img, page, w, h: ([], [], [], []))
    return folder


def test_flag_absent_writes_no_pngs(tmp_path, monkeypatch):
    folder = _stub_document(tmp_path, monkeypatch, page_count=2)
    # default: write_page_images=False
    pipeline.run(pipeline.Invocation(document_folder=folder))
    pngs = list(folder.glob("page_*.png"))
    assert pngs == [], (
        f"FR-022: --write-page-images is opt-in; no PNGs should be written without "
        f"the flag, but found: {[p.name for p in pngs]}"
    )
    # The artifact itself must still be produced (FR-022 is PNG-only, not JSON).
    assert (folder / "preprocess_output.json").is_file()


def test_flag_present_writes_one_png_per_page(tmp_path, monkeypatch):
    folder = _stub_document(tmp_path, monkeypatch, page_count=3)
    pipeline.run(
        pipeline.Invocation(document_folder=folder, write_page_images=True)
    )
    pngs = sorted(p.name for p in folder.glob("page_*.png"))
    assert pngs == ["page_1.png", "page_2.png", "page_3.png"]
    # Teardown — don't litter the tmp tree (pytest handles tmp_path, but explicit
    # cleanup keeps local reruns idempotent if tmp_path_factory caches).
    for name in pngs:
        (folder / name).unlink()


def test_flag_absent_artifact_still_validates_structurally(tmp_path, monkeypatch):
    """FR-004 / FR-022: the JSON artifact is byte-identical across --write-page-images
    states because FR-004 scopes determinism to preprocess_output.json only. A
    quick sanity check: artifact is produced and parseable either way."""
    folder = _stub_document(tmp_path, monkeypatch, page_count=1)
    pipeline.run(pipeline.Invocation(document_folder=folder))
    data = json.loads((folder / "preprocess_output.json").read_text(encoding="utf-8"))
    assert data["document_id"] == "inv_099"
    assert data["page_count"] == 1
