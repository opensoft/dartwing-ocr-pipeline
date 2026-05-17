"""Structural section: pages passthrough + flattened reading_order + document_text."""
from __future__ import annotations

from typing import Any

from dartwing_ocr.evidence_packet.errors import PacketAssemblyError
from dartwing_ocr.evidence_packet.offset_mapping import (
    _sorted_blocks,
    _sorted_pages,
    build_offset_index,
)


def build_structural_section(
    preprocess_output: dict[str, Any],
) -> tuple[dict[str, Any], list[tuple[int, int, int, int]]]:
    """Return (structural_dict, offset_spans).

    The packet carries the offset spans forward so the candidate-signals
    builder can reverse-map regex offsets without re-walking the pages.
    """
    pages = preprocess_output["pages"]
    ordered_pages = _sorted_pages(pages)

    reading_order: list[str] = []
    for page in ordered_pages:
        for block in _sorted_blocks(page):
            reading_order.append(block["block_id"])

    document_text, spans = build_offset_index(pages)
    if document_text != preprocess_output["document_text"]:
        raise PacketAssemblyError(
            "rebuilt document_text does not match preprocess_output['document_text'] "
            "(deterministic join must agree byte-for-byte)"
        )

    return (
        {
            "pages": ordered_pages,
            "reading_order": reading_order,
            "document_text": document_text,
        },
        spans,
    )
