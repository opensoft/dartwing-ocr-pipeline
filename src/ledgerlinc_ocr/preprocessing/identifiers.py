"""Page-scoped identifier minting (FR-008, FR-009, FR-009a, research Decision 5)."""

from __future__ import annotations


def block_id(page_number: int, reading_order: int) -> str:
    if page_number < 1 or reading_order < 1:
        raise ValueError(f"page_number and reading_order must be >= 1, got {page_number=}, {reading_order=}")
    return f"p{page_number}_b{reading_order}"


def line_id(page_number: int, line_index: int) -> str:
    if page_number < 1 or line_index < 1:
        raise ValueError(f"page_number and line_index must be >= 1, got {page_number=}, {line_index=}")
    return f"p{page_number}_l{line_index}"
