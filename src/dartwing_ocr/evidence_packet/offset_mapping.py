"""Deterministic document_text reconstruction + offset → (page,block,line) mapping.

The join semantics exactly match ``dartwing_ocr.preprocessing.document_text``
(INTRA_PAGE_SEPARATOR="\\n", INTER_PAGE_SEPARATOR="\\n\\n", pages sorted by
``page_number``, blocks sorted by ``reading_order``). That's the contract
``document_text`` rides on; any drift breaks offset integrity.
"""
from __future__ import annotations

import bisect
from typing import Any

from dartwing_ocr.preprocessing.document_text import (
    INTER_PAGE_SEPARATOR,
    INTRA_PAGE_SEPARATOR,
)


# Each entry: (block_start_offset, block_end_offset, page_index, block_index).
BlockSpan = tuple[int, int, int, int]


def _sorted_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(pages, key=lambda p: p["page_number"])


def _sorted_blocks(page: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(page.get("blocks", []), key=lambda b: b["reading_order"])


def build_offset_index(pages: list[dict[str, Any]]) -> tuple[str, list[BlockSpan]]:
    """Rebuild document_text and record block-span offsets simultaneously."""
    ordered_pages = _sorted_pages(pages)
    spans: list[BlockSpan] = []
    cursor = 0
    page_parts: list[str] = []

    for page_idx, page in enumerate(ordered_pages):
        blocks = _sorted_blocks(page)
        block_parts: list[str] = []
        page_start = cursor
        for block_idx, block in enumerate(blocks):
            text = block["text"]
            block_start = cursor
            block_end = block_start + len(text)
            spans.append((block_start, block_end, page_idx, block_idx))
            block_parts.append(text)
            cursor = block_end
            if block_idx < len(blocks) - 1:
                cursor += len(INTRA_PAGE_SEPARATOR)
        page_parts.append(INTRA_PAGE_SEPARATOR.join(block_parts))
        if page_idx < len(ordered_pages) - 1:
            # Move cursor past the page separator so the next page's block
            # spans start at the correct offset.
            cursor = page_start + len(page_parts[-1]) + len(INTER_PAGE_SEPARATOR)

    document_text = INTER_PAGE_SEPARATOR.join(page_parts)
    return document_text, spans


def reverse_map(
    offset: int,
    spans: list[BlockSpan],
    pages: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Return (page_index, block_index, line_index) for a document_text offset.

    ``line_index`` is the number of '\\n' characters within the block's text
    that precede the offset.
    """
    starts = [span[0] for span in spans]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        raise ValueError(f"offset {offset} precedes the first block span")
    block_start, _block_end, page_idx, block_idx = spans[idx]

    ordered_pages = _sorted_pages(pages)
    block = _sorted_blocks(ordered_pages[page_idx])[block_idx]
    within = offset - block_start
    line_idx = block["text"][:within].count("\n")
    return page_idx, block_idx, line_idx
