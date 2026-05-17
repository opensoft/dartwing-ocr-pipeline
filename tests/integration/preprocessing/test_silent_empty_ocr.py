"""FR-019 silent-empty-ocr: layout produces text-type blocks but OCR returns zero lines.

Symmetric to FR-003 — missing evidence on either axis downgrades the document.
"""

from __future__ import annotations

import json
from pathlib import Path

from dartwing_ocr.preprocessing import ocr, pipeline


def _fake_text_blocks_no_lines(image, page_number, width, height):
    blocks = [
        {
            "block_id": f"p{page_number}_b1",
            "block_type": "title",
            "bbox": [10, 10, 200, 40],
            "reading_order": 1,
            "text": "",
            "confidence": 0.88,
        },
        {
            "block_id": f"p{page_number}_b2",
            "block_type": "text",
            "bbox": [10, 50, 300, 150],
            "reading_order": 2,
            "text": "",
            "confidence": 0.81,
        },
    ]
    return [], blocks, [], []


def _fake_figure_only_no_lines(image, page_number, width, height):
    """Figure-only page legitimately has zero OCR lines — MUST NOT fire FR-019."""
    blocks = [
        {
            "block_id": f"p{page_number}_b1",
            "block_type": "figure",
            "bbox": [10, 10, 200, 200],
            "reading_order": 1,
            "text": "",
            "confidence": 0.75,
        },
    ]
    return [], blocks, [], []


def test_silent_empty_ocr_emits_warning_and_downgrades(monkeypatch, us1_workdir: Path):
    monkeypatch.setattr(ocr, "run_page", _fake_text_blocks_no_lines)
    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    art = json.loads(out.read_text(encoding="utf-8"))

    categorized = [w for w in art["warnings"] if "[silent_empty_ocr]" in w]
    assert len(categorized) == 1, art["warnings"]
    assert categorized[0] == (
        "page 1: [silent_empty_ocr] OCR returned zero lines despite 2 text-type blocks"
    )
    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "failure"


def test_figure_only_page_does_not_fire_fr019(monkeypatch, us1_workdir: Path):
    """A page whose only blocks are `figure` or `table` has no text-bearing blocks;
    zero OCR lines is legitimate and MUST NOT trigger FR-019 or downgrade status."""
    monkeypatch.setattr(ocr, "run_page", _fake_figure_only_no_lines)
    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    art = json.loads(out.read_text(encoding="utf-8"))

    categorized = [w for w in art["warnings"] if "[silent_empty_ocr]" in w]
    assert categorized == []
    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "success"
