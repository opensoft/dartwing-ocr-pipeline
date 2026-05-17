"""Feature 020 / T006 / R-020.5: y-coordinate header-band filter tests.

Asserts:

- Tokens with ``bbox_top_y / page_height < Y_THRESHOLD_FRACTION (0.25)``
  are in-band.
- Tokens at or above the boundary are out-of-band (strict-less-than
  comparison).
- Multi-page documents only see ``pages[0]`` tokens.
"""

from __future__ import annotations

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    Y_THRESHOLD_FRACTION,
    compute_five_signals,
)


def _doc(blocks_page0: list[dict], blocks_page1: list[dict] | None = None,
         page_height: int = 1000) -> dict:
    pages = [
        {
            "page_number": 1, "width": 1000, "height": page_height,
            "rotation_detected": 0,
            "blocks": blocks_page0,
            "raw_ocr_lines": [],
        }
    ]
    if blocks_page1 is not None:
        pages.append({
            "page_number": 2, "width": 1000, "height": page_height,
            "rotation_detected": 0,
            "blocks": blocks_page1,
            "raw_ocr_lines": [],
        })
    return {"pages": pages}


def test_y_threshold_constant_is_pinned_to_quarter() -> None:
    """R-020.5 / data-model.md Appendix A: pinned value at landing."""
    assert Y_THRESHOLD_FRACTION == 0.25


def test_token_strictly_below_threshold_is_in_band() -> None:
    """Token at y=100 with page_height=1000 → ratio 0.10 < 0.25 → in-band."""
    doc = _doc(
        [
            {"text": "InHeader", "confidence": 0.9, "bbox": [0, 100, 100, 150]},
        ],
        page_height=1000,
    )
    s = compute_five_signals(doc)
    assert s.header_band_token_density == 1


def test_token_at_threshold_boundary_is_out_of_band() -> None:
    """R-020.5 strict-less-than comparison: token at exactly 0.25 is the
    page body, NOT the header."""
    doc = _doc(
        [
            # y_top = 250 on a 1000-height page → ratio 0.25 (NOT < 0.25).
            {"text": "BoundaryToken", "confidence": 0.9, "bbox": [0, 250, 100, 300]},
        ],
        page_height=1000,
    )
    s = compute_five_signals(doc)
    assert s.header_band_token_density == 0


def test_token_above_threshold_is_out_of_band() -> None:
    """Token at y=500 with page_height=1000 → ratio 0.5 > 0.25 → out-of-band."""
    doc = _doc(
        [
            {"text": "InBody", "confidence": 0.9, "bbox": [0, 500, 100, 600]},
        ],
        page_height=1000,
    )
    s = compute_five_signals(doc)
    assert s.header_band_token_density == 0


def test_mixed_blocks_only_in_band_counted() -> None:
    """In-band and out-of-band blocks: only in-band contribute."""
    doc = _doc(
        [
            {"text": "Header One Two", "confidence": 0.9, "bbox": [0, 100, 100, 200]},
            {"text": "Body Three Four Five", "confidence": 0.9, "bbox": [0, 400, 100, 500]},
        ],
        page_height=1000,
    )
    s = compute_five_signals(doc)
    # Only the first block's 3 tokens are in-band.
    assert s.header_band_token_density == 3


def test_multipage_only_page0_considered() -> None:
    """Page 2 tokens MUST NOT be considered (R-020.5 multi-page rule)."""
    doc = _doc(
        blocks_page0=[
            {"text": "Page0Header", "confidence": 0.9, "bbox": [0, 100, 100, 200]},
        ],
        blocks_page1=[
            {"text": "Page1Header AlsoIgnored Tokens", "confidence": 0.9, "bbox": [0, 50, 100, 100]},
        ],
        page_height=1000,
    )
    s = compute_five_signals(doc)
    # Only page-0's 1 token counts.
    assert s.header_band_token_density == 1


def test_dimension_invariant_fraction_works_on_a4() -> None:
    """A4 page (height 1190 pt) — the 25% threshold scales correctly."""
    doc = _doc(
        [
            {"text": "Token", "confidence": 0.9, "bbox": [0, 100, 100, 200]},
        ],
        page_height=1190,
    )
    s = compute_five_signals(doc)
    # 100 / 1190 = 0.084 < 0.25 → in-band.
    assert s.header_band_token_density == 1


def test_dimension_invariant_fraction_works_on_us_letter() -> None:
    """US Letter page (height 792 pt) — the 25% threshold scales correctly."""
    doc = _doc(
        [
            # y_top=200, page_height=792 → 0.253 (just outside 0.25).
            {"text": "JustOutside", "confidence": 0.9, "bbox": [0, 200, 100, 300]},
            # y_top=150, page_height=792 → 0.189 < 0.25 → in-band.
            {"text": "InsideToken", "confidence": 0.9, "bbox": [0, 150, 100, 200]},
        ],
        page_height=792,
    )
    s = compute_five_signals(doc)
    assert s.header_band_token_density == 1
