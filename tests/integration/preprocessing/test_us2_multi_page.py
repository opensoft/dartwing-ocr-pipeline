"""US2 — multi-page PDF determinism.

Covers FR-009a (page-scoped identifiers), FR-006 (rotation warning format),
and the document_text concatenation rule from US1 AC#5 extended across pages.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


def test_ac1_page_count_and_unique_ids(us2_three_page_artifact):
    art = us2_three_page_artifact
    assert art["page_count"] == 3
    assert [p["page_number"] for p in art["pages"]] == [1, 2, 3]

    block_ids: list[str] = []
    line_ids: list[str] = []
    for page in art["pages"]:
        n = page["page_number"]
        for b in page["blocks"]:
            assert b["block_id"].startswith(f"p{n}_b"), b["block_id"]
            block_ids.append(b["block_id"])
        for line in page["raw_ocr_lines"]:
            assert line["line_id"].startswith(f"p{n}_l"), line["line_id"]
            line_ids.append(line["line_id"])

    assert len(block_ids) == len(set(block_ids)), "block_id must be unique across document"
    assert len(line_ids) == len(set(line_ids)), "line_id must be unique across document"


def test_ac1_two_page_page_count(us2_two_page_artifact):
    assert us2_two_page_artifact["page_count"] == 2
    assert [p["page_number"] for p in us2_two_page_artifact["pages"]] == [1, 2]


def test_ac2_reading_order_per_page(us2_three_page_artifact):
    for page in us2_three_page_artifact["pages"]:
        orders = sorted(b["reading_order"] for b in page["blocks"])
        if orders:
            assert orders == list(range(1, len(orders) + 1)), (
                f"page {page['page_number']} reading_order not contiguous from 1: {orders}"
            )


def test_ac3_per_page_dimensions_independent(us2_three_page_artifact):
    art = us2_three_page_artifact
    page1 = art["pages"][0]
    page2 = art["pages"][1]
    page3 = art["pages"][2]

    for p in (page1, page2, page3):
        assert p["width"] >= 1 and p["height"] >= 1
        assert p["rotation_detected"] in {0, 90, 180, 270}
        assert p["rotation_detected"] == 0  # Pillow-written PDFs are 0° native

    # Page 2 is landscape — width must exceed height; page 1/3 are portrait.
    assert page2["width"] > page2["height"]
    assert page1["height"] > page1["width"]
    assert page3["height"] > page3["width"]


def test_ac3_rotation_warning_format(tmp_path, monkeypatch):
    """FR-006: warning string format is pinned."""
    from ledgerlinc_ocr.preprocessing import ocr, pipeline, rasterize
    from ledgerlinc_ocr.preprocessing.rasterize import PageRaster
    from PIL import Image

    folder = tmp_path / "inv_099"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%stub\n")

    fake_image = Image.new("RGB", (100, 100), "white")
    fake_pages = [
        PageRaster(
            page_number=1,
            width=100,
            height=100,
            rotation_detected=90,
            rotation_original=87,
            rotation_snapped=True,
            image=fake_image,
        ),
    ]

    monkeypatch.setattr(rasterize, "rasterize_pdf", lambda pdf_path, dpi: fake_pages)
    monkeypatch.setattr(ocr, "run_ocr_lines", lambda img, page, w, h: ([], []))
    monkeypatch.setattr(ocr, "run_layout", lambda img, page, w, h: ([], [], []))

    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    art = json.loads(out.read_text(encoding="utf-8"))

    expected = "page 1: rotation 87° normalized to 90°"
    assert expected in art["warnings"], art["warnings"]


def test_ac4_document_text_concat(us2_three_page_artifact):
    art = us2_three_page_artifact
    doc_text = art["document_text"]
    assert isinstance(doc_text, str)

    per_page_texts: list[str] = []
    for page in sorted(art["pages"], key=lambda p: p["page_number"]):
        blocks = sorted(page["blocks"], key=lambda b: b["reading_order"])
        per_page_texts.append("\n".join(b["text"] for b in blocks))
    expected = "\n\n".join(per_page_texts)
    assert doc_text == expected, (doc_text, expected)
