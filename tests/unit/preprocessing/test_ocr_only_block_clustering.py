"""Feature 019 / T014 / R-019.8 / I-019.6 / I-019.8: CPU-safe tests for
deterministic Y-axis block clustering in `preprocessing/ocr_only.py`.
"""

from __future__ import annotations

import pytest

from dartwing_ocr.preprocessing.ocr_only import (
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
    """One line ⇒ one block; bbox = line bbox; text = line text;
    mean_confidence = line's detector_confidence verbatim."""
    line = _line(10, 20, 100, 30, text="Acme", conf=0.9)
    blocks = cluster_lines_into_blocks([line])
    assert len(blocks) == 1
    b = blocks[0]
    assert b.bbox == (10, 20, 100, 30)
    assert b.text == "Acme"
    assert b.block_type == "text"  # I-019.6
    assert b.mean_confidence == pytest.approx(0.9)


def test_close_lines_cluster_into_one_block() -> None:
    """Two lines within 1.5 * H cy distance ⇒ single block."""
    # Each line has height ten; vertical centers fifteen and twenty-seven give distance twelve, within the threshold of fifteen.
    l1 = _line(0, 10, 100, 20, text="Acme")
    l2 = _line(0, 22, 100, 32, text="Corp")
    blocks = cluster_lines_into_blocks([l1, l2])
    assert len(blocks) == 1
    assert blocks[0].text == "Acme\nCorp"
    # bbox is envelope
    assert blocks[0].bbox == (0, 10, 100, 32)


def test_far_lines_split_into_separate_blocks() -> None:
    """Two lines with cy distance > 1.5 * H ⇒ two separate blocks."""
    # Each line has height ten; centers fifteen and two hundred give distance one hundred eighty-five, far above the fifteen-pixel threshold.
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


# ---------------------------------------------------------------------------
# Boundary cases added by pre-PR QA review (R-019.8 / I-019.8 edge coverage)
# ---------------------------------------------------------------------------


def test_cy_distance_exactly_equals_threshold_clusters_together() -> None:
    """Inclusive `<=` comparison: cy distance == 1.5 * median_height MUST
    cluster (the threshold edge is part of the same-block half-space)."""
    # Two height-ten lines yield a median height of ten and a fifteen-pixel proximity threshold.
    # The first line's vertical center sits at fifteen and the second at thirty, giving a
    # distance of fifteen — exactly at the inclusive threshold.
    l1 = _line(0, 10, 100, 20, text="A")
    l2 = _line(0, 25, 100, 35, text="B")
    blocks = cluster_lines_into_blocks([l1, l2])
    assert len(blocks) == 1, (
        "cy distance == 1.5 * median_height should cluster (inclusive edge)"
    )
    assert blocks[0].text == "A\nB"


def test_cy_distance_one_greater_than_threshold_splits() -> None:
    """One unit past the inclusive threshold MUST split into two blocks
    (the strict-less-or-equal boundary)."""
    # Height ten gives a fifteen-pixel threshold; centers at fifteen and thirty-one yield distance sixteen, just over the threshold.
    l1 = _line(0, 10, 100, 20, text="A")
    l2 = _line(0, 26, 100, 36, text="B")
    blocks = cluster_lines_into_blocks([l1, l2])
    assert len(blocks) == 2


def test_all_zero_height_lines_do_not_collapse_to_zero_threshold() -> None:
    """If every input line has zero height (degenerate OCR output), the
    proximity threshold MUST be clamped to a non-zero floor — otherwise
    every line would split into its own block (pre-PR QA review #11 /
    edge case for malformed inputs)."""
    # All input lines have identical top and bottom, producing zero-height boxes and a zero median.
    # Without the floor clamp the proximity threshold would collapse to zero and a one-pixel gap
    # would force a split; the clamp lifts the threshold to one-and-a-half pixels so adjacent centers
    # lines still cluster.
    # Both bboxes are zero-height; the first has vertical center one hundred and the second
    # has vertical center one hundred and one.
    lines = [
        _line(0, 100, 50, 100, text="A"),
        _line(60, 101, 100, 101, text="B"),
    ]
    blocks = cluster_lines_into_blocks(lines)
    assert len(blocks) == 1, (
        "all-zero-height input must not collapse the proximity threshold "
        "to 0; clamp ensures lines with a 1px cy gap still cluster"
    )


def test_block_carries_cluster_local_mean_confidence() -> None:
    """Per pre-PR QA review #7: `OcrOnlyBlock.mean_confidence` is the
    arithmetic mean of the cluster's member-line detector_confidence
    values (cluster-local, NOT page-mean)."""
    # Two clusters; high-confidence in one, low-confidence in the other.
    lines = [
        _line(0, 10, 100, 20, text="A", conf=0.9),    # cluster 1
        _line(0, 22, 100, 32, text="B", conf=0.95),   # cluster 1
        _line(0, 200, 100, 210, text="C", conf=0.3),  # cluster 2
        _line(0, 212, 100, 222, text="D", conf=0.35), # cluster 2
    ]
    blocks = cluster_lines_into_blocks(lines)
    assert len(blocks) == 2
    # Cluster 1 mean: (0.9 + 0.95) / 2 = 0.925
    assert blocks[0].mean_confidence == pytest.approx(0.925)
    # Cluster 2 mean: (0.3 + 0.35) / 2 = 0.325
    assert blocks[1].mean_confidence == pytest.approx(0.325)
    # The means MUST differ — proves it's cluster-local, not page-mean
    # (page-mean would be (0.9+0.95+0.3+0.35)/4 = 0.625 for both blocks).
    assert blocks[0].mean_confidence != blocks[1].mean_confidence
