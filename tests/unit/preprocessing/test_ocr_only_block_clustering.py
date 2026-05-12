"""Feature 019 / T014 / R-019.8 / I-019.6 / I-019.8: CPU-safe tests for
deterministic Y-axis block clustering in `preprocessing/ocr_only.py`.
"""

from __future__ import annotations

from ledgerlinc_ocr.preprocessing.ocr_only import (
    OcrOnlyLine,
    cluster_lines_into_blocks,
)


def _line(x0: int, y0: int, x1: int, y1: int, text: str = "x", conf: float = 0.9) -> OcrOnlyLine:
    return OcrOnlyLine(bbox=(x0, y0, x1, y1), text=text, detector_confidence=conf)


# ---------------------------------------------------------------------------
# Boundary cases (R-019.8)
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty() -> None:
    """Empty lines list ⇒ empty blocks list (R-019.8 boundary)."""
    assert cluster_lines_into_blocks([]) == []


def test_single_line_yields_single_block() -> None:
    """One line ⇒ one block; bbox = line bbox; text = line text."""
    line = _line(10, 20, 100, 30, text="Acme")
    blocks = cluster_lines_into_blocks([line])
    assert len(blocks) == 1
    b = blocks[0]
    assert b.bbox == (10, 20, 100, 30)
    assert b.text == "Acme"
    assert b.block_type == "text"  # I-019.6


def test_close_lines_cluster_into_one_block() -> None:
    """Two lines within 1.5 * H cy distance ⇒ single block."""
    # Line heights = 10; cy[0]=15, cy[1]=27 → distance=12 ≤ 1.5*10=15
    l1 = _line(0, 10, 100, 20, text="Acme")
    l2 = _line(0, 22, 100, 32, text="Corp")
    blocks = cluster_lines_into_blocks([l1, l2])
    assert len(blocks) == 1
    assert blocks[0].text == "Acme\nCorp"
    # bbox is envelope
    assert blocks[0].bbox == (0, 10, 100, 32)


def test_far_lines_split_into_separate_blocks() -> None:
    """Two lines with cy distance > 1.5 * H ⇒ two separate blocks."""
    # Heights=10; cy[0]=15, cy[1]=200 → distance=185 > 1.5*10=15
    l1 = _line(0, 10, 100, 20, text="Top")
    l2 = _line(0, 195, 100, 205, text="Bottom")
    blocks = cluster_lines_into_blocks([l1, l2])
    assert len(blocks) == 2
    assert blocks[0].text == "Top"
    assert blocks[1].text == "Bottom"
    # Ordering is top-to-bottom (cy ascending)
    assert blocks[0].bbox[1] < blocks[1].bbox[1]


def test_all_blocks_have_text_block_type() -> None:
    """Every block emitted is `block_type="text"` per I-019.6 — OCR-only
    never emits other layout-derived block types."""
    lines = [_line(0, 0, 100, 10), _line(0, 200, 100, 210)]
    blocks = cluster_lines_into_blocks(lines)
    for b in blocks:
        assert b.block_type == "text"


def test_determinism_repeat_input() -> None:
    """Two runs with the same input produce identical Block objects (I-019.8)."""
    lines = [
        _line(0, 10, 100, 20, text="A"),
        _line(0, 30, 100, 40, text="B"),
        _line(0, 200, 100, 210, text="C"),
    ]
    b1 = cluster_lines_into_blocks(lines)
    b2 = cluster_lines_into_blocks(lines)
    assert b1 == b2


def test_lines_sorted_by_cy_ascending() -> None:
    """Input order doesn't matter — clusters built by cy-sorted order."""
    # Provide reverse-order; expect ascending cy in output blocks
    lines = [
        _line(0, 200, 100, 210, text="Z"),
        _line(0, 10, 100, 20, text="A"),
    ]
    blocks = cluster_lines_into_blocks(lines)
    # Two separate blocks; first is the one with smaller cy
    assert len(blocks) == 2
    assert blocks[0].text == "A"
    assert blocks[1].text == "Z"


def test_three_close_lines_form_one_block() -> None:
    """Three vertically-stacked lines within proximity ⇒ one 3-line block."""
    lines = [
        _line(0, 10, 100, 20, text="Acme"),
        _line(0, 22, 100, 32, text="Bills"),
        _line(0, 34, 100, 44, text="Payable"),
    ]
    blocks = cluster_lines_into_blocks(lines)
    assert len(blocks) == 1
    assert blocks[0].text == "Acme\nBills\nPayable"


def test_reading_order_is_sequential() -> None:
    """Block.reading_order is 1-indexed cluster index in cy order."""
    lines = [
        _line(0, 10, 100, 20, text="A"),
        _line(0, 200, 100, 210, text="B"),
        _line(0, 400, 100, 410, text="C"),
    ]
    blocks = cluster_lines_into_blocks(lines)
    assert [b.reading_order for b in blocks] == [1, 2, 3]
