"""FR-004 verbatim-encoding axes: bbox integer rounding and Unicode non-normalization.

Pairs with the T051 audit in `src/dartwing_ocr/preprocessing/ocr.py`. The
spec pins two rules for byte-stable output whose violations would be visible
only under pathological inputs (off-integer polys, non-ASCII glyphs):

  1. bbox integer encoding via `floor` on min-axes, `ceil` on max-axes, clipped
     to `[0, width]` / `[0, height]`.
  2. No `unicodedata.normalize(...)` (NFC or NFD) applied to `block.text`,
     `raw_ocr_lines[].text`, or `document_text`.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from dartwing_ocr.preprocessing.ocr import _bbox_from_coord, _clip_bbox


class TestClipBbox:
    def test_floor_min_ceil_max_on_off_integer_polys(self):
        # Worked example from tasks.md T054a:
        # [(1.4, 2.6), (10.9, 20.1)] on a 12x22 page → (1, 2, 11, 21).
        coord = [(1.4, 2.6), (10.9, 2.6), (10.9, 20.1), (1.4, 20.1)]
        bbox = _bbox_from_coord(coord)
        assert bbox == [1, 2, 11, 21]
        clipped = _clip_bbox(bbox, width=12, height=22)
        assert clipped == [1, 2, 11, 21]

    def test_floor_takes_floor_even_when_close_to_next_integer(self):
        # x0=1.99 → floor=1; x1=2.01 → ceil=3.
        coord = [(1.99, 0.0), (2.01, 0.0), (2.01, 1.0), (1.99, 1.0)]
        bbox = _bbox_from_coord(coord)
        assert bbox[0] == 1
        assert bbox[2] == 3

    def test_clip_to_page_bounds_upper(self):
        clipped = _clip_bbox([-3, -5, 150, 250], width=100, height=200)
        assert clipped == [0, 0, 100, 200]

    def test_clip_non_negative(self):
        clipped = _clip_bbox([-10, -10, 5, 5], width=100, height=100)
        assert clipped == [0, 0, 5, 5]

    def test_clip_returns_integers(self):
        clipped = _clip_bbox([1, 2, 3, 4], width=100, height=100)
        assert all(isinstance(v, int) for v in clipped)


class TestTextVerbatim:
    """FR-004: no NFC / NFD normalization on text fields."""

    def test_nfc_and_nfd_forms_differ(self):
        precomposed = "é"  # U+00E9, single code point
        combining = "é"  # U+0065 + U+0301
        assert precomposed != combining
        assert unicodedata.normalize("NFC", combining) == precomposed
        assert unicodedata.normalize("NFD", precomposed) == combining

    def test_json_roundtrip_preserves_precomposed(self):
        s = "é"
        out = json.loads(json.dumps(s, ensure_ascii=False))
        assert out == s
        assert out != "é"

    def test_json_roundtrip_preserves_combining(self):
        s = "é"
        out = json.loads(json.dumps(s, ensure_ascii=False))
        assert out == s
        assert out != "é"

    def test_preprocessing_sources_do_not_call_unicodedata_normalize(self):
        """Guard: no preprocessing source file imports or calls
        `unicodedata.normalize(...)`. FR-004's "text verbatim" rule forbids
        silent NFC/NFD transformations during artifact construction.
        """
        src_root = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "dartwing_ocr"
            / "preprocessing"
        )
        assert src_root.is_dir(), f"preprocessing source root missing: {src_root}"
        offenders: list[str] = []
        for py in src_root.glob("*.py"):
            content = py.read_text(encoding="utf-8")
            if "unicodedata.normalize" in content:
                offenders.append(py.name)
            if "from unicodedata import normalize" in content:
                offenders.append(py.name)
        assert offenders == [], (
            f"Preprocessing source files call unicodedata.normalize: {offenders}. "
            "FR-004 requires verbatim text persistence with no NFC/NFD normalization."
        )
