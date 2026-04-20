"""Deterministic document_text assembly (FR-010, research Decision 4)."""

from __future__ import annotations

from typing import Any, Iterable

INTRA_PAGE_SEPARATOR = "\n"
INTER_PAGE_SEPARATOR = "\n\n"


def join_document_text(pages: Iterable[dict[str, Any]]) -> str:
    ordered = sorted(pages, key=lambda p: p["page_number"])
    parts: list[str] = []
    for page in ordered:
        blocks = sorted(page.get("blocks", []), key=lambda b: b["reading_order"])
        parts.append(INTRA_PAGE_SEPARATOR.join(b["text"] for b in blocks))
    return INTER_PAGE_SEPARATOR.join(parts)
