"""Unit tests for ``offset_mapping``: join parity + reverse_map correctness."""
from __future__ import annotations

import pytest

from dartwing_ocr.evidence_packet.offset_mapping import (
    build_offset_index,
    reverse_map,
)
from dartwing_ocr.preprocessing.document_text import join_document_text


def _page(page_number: int, *block_texts: str) -> dict:
    return {
        "page_number": page_number,
        "width": 100,
        "height": 100,
        "rotation_detected": 0,
        "blocks": [
            {
                "block_id": f"p{page_number}_b{i+1}",
                "block_type": "text",
                "bbox": [0, 0, 10, 10],
                "reading_order": i,
                "text": text,
                "confidence_mean": 0.9,
            }
            for i, text in enumerate(block_texts)
        ],
        "raw_ocr_lines": [],
    }


def test_build_offset_index_matches_join_document_text():
    pages = [
        _page(1, "Hello world", "Second block"),
        _page(2, "Third line\nfourth", "Fifth"),
    ]
    document_text, spans = build_offset_index(pages)
    assert document_text == join_document_text(pages)

    for block_start, block_end, page_idx, block_idx in spans:
        page = sorted(pages, key=lambda p: p["page_number"])[page_idx]
        block = sorted(page["blocks"], key=lambda b: b["reading_order"])[block_idx]
        assert document_text[block_start:block_end] == block["text"]


def test_reverse_map_at_block_boundaries_and_mid_block():
    pages = [_page(1, "alpha", "beta")]
    document_text, spans = build_offset_index(pages)
    # document_text == "alpha\nbeta"
    assert document_text == "alpha\nbeta"

    # Offset at start of block 0
    assert reverse_map(0, spans, pages) == (0, 0, 0)
    # Offset within block 0
    assert reverse_map(3, spans, pages) == (0, 0, 0)
    # Offset at start of block 1 ("b" of "beta")
    assert reverse_map(6, spans, pages) == (0, 1, 0)
    # Offset mid block 1
    assert reverse_map(8, spans, pages) == (0, 1, 0)


def test_reverse_map_line_index_counts_newlines_within_block():
    pages = [_page(1, "first\nsecond\nthird")]
    document_text, spans = build_offset_index(pages)
    assert document_text == "first\nsecond\nthird"

    # Offset 0 → line 0
    assert reverse_map(0, spans, pages) == (0, 0, 0)
    # Offset at "second" → line 1
    assert reverse_map(6, spans, pages) == (0, 0, 1)
    # Offset at "third" → line 2
    assert reverse_map(13, spans, pages) == (0, 0, 2)


def test_reverse_map_crosses_pages():
    pages = [_page(1, "page-one"), _page(2, "page-two")]
    document_text, spans = build_offset_index(pages)
    assert document_text == "page-one\n\npage-two"

    # Start of page 2's first block is at offset 10
    assert reverse_map(10, spans, pages) == (1, 0, 0)


def test_reverse_map_negative_offset_raises():
    pages = [_page(1, "alpha")]
    _, spans = build_offset_index(pages)
    with pytest.raises(ValueError):
        reverse_map(-1, spans, pages)
