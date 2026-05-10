"""Feature 018 (T024 / R-018.15 / I-018.7): CPU-safe unit tests for the
`region_strategies.translate_bbox` coordinate-translation helper.

The helper translates PaddleOCR-returned crop-relative pixel bboxes
back to full-page pixel coordinates by adding the crop's top-left
offset. For `header-first-v1` the crop is at page top-left so the
offset is `(0, 0)` (identity); the helper exists as a guard rail for
any future preset that crops a non-top-left region.

All tests are CPU-safe.
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.region_strategies import translate_bbox


def test_translate_bbox_with_zero_offset_is_identity() -> None:
    """For header-first-v1's `(0, 0)` offset, translate_bbox is the
    identity — bbox values are unchanged."""
    bbox = (10, 20, 30, 40)
    assert translate_bbox(bbox, (0, 0)) == bbox


def test_translate_bbox_adds_offset_to_all_four_coordinates() -> None:
    """Translation is `(x0+dx, y0+dy, x1+dx, y1+dy)`."""
    assert translate_bbox((10, 20, 30, 40), (100, 200)) == (110, 220, 130, 240)


def test_translate_bbox_handles_zero_origin_bbox() -> None:
    """A bbox starting at the crop's top-left (`x0=y0=0`) translates
    to the crop's offset in full-page coordinates."""
    assert translate_bbox((0, 0, 50, 50), (200, 300)) == (200, 300, 250, 350)


def test_translate_bbox_preserves_width_and_height() -> None:
    """Translation is a pure shift — width (x1 - x0) and height
    (y1 - y0) are preserved."""
    bbox = (10, 20, 100, 200)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    translated = translate_bbox(bbox, (50, 75))
    assert translated[2] - translated[0] == width
    assert translated[3] - translated[1] == height


@pytest.mark.parametrize(
    "offset_x, offset_y",
    [
        (0, 0),
        (1, 0),
        (0, 1),
        (100, 200),
        (1234, 5678),
    ],
)
def test_translate_bbox_arbitrary_offsets(offset_x: int, offset_y: int) -> None:
    """The helper works for arbitrary integer offsets."""
    bbox = (5, 10, 15, 20)
    translated = translate_bbox(bbox, (offset_x, offset_y))
    assert translated == (
        5 + offset_x,
        10 + offset_y,
        15 + offset_x,
        20 + offset_y,
    )


def test_translate_bbox_returns_tuple_not_list() -> None:
    """The return type is a 4-tuple (immutable, hashable)."""
    result = translate_bbox((10, 20, 30, 40), (5, 10))
    assert isinstance(result, tuple)
    assert len(result) == 4
