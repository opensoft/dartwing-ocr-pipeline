"""FR-004 / R-013: confidence persisted when valid, missing → None.

Covers the `_persist_confidence` / `_persist_confidence_value` helpers that
preserve in-range engine values without silently clamping invalid ones. Pairs
with the T051 audit of `src/ledgerlinc_ocr/preprocessing/ocr.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ledgerlinc_ocr.preprocessing.ocr import (
    _extract_lines,
    _persist_confidence,
    _persist_confidence_value,
)


class TestPersistConfidenceValue:
    def test_numeric_round_trip(self):
        assert _persist_confidence_value(0.85) == pytest.approx(0.85)

    def test_int_coerces_to_float(self):
        result = _persist_confidence_value(1)
        assert result == pytest.approx(1.0)
        assert isinstance(result, float)

    def test_out_of_range_returns_none_without_clamping(self):
        assert _persist_confidence_value(1.2) is None
        assert _persist_confidence_value(-0.1) is None
        assert _persist_confidence_value(42.0) is None

    def test_none_returns_none(self):
        assert _persist_confidence_value(None) is None

    def test_non_numeric_returns_none(self):
        assert _persist_confidence_value("oops") is None
        assert _persist_confidence_value(object()) is None

    def test_none_never_becomes_zero(self):
        """Constitution's null discipline: missing → null, never 0.0."""
        assert _persist_confidence_value(None) is None


class TestPersistConfidence:
    def test_numeric_round_trip(self):
        assert _persist_confidence([0.85, 0.72], 0) == pytest.approx(0.85)
        assert _persist_confidence([0.85, 0.72], 1) == pytest.approx(0.72)

    def test_out_of_range_returns_none_without_clamping(self):
        assert _persist_confidence([1.2], 0) is None
        assert _persist_confidence([-0.1], 0) is None

    def test_missing_index_returns_none(self):
        assert _persist_confidence([0.8, 0.9], 2) is None
        assert _persist_confidence([], 0) is None

    def test_none_value_returns_none(self):
        assert _persist_confidence([None, 0.9], 0) is None

    def test_non_numeric_returns_none(self):
        assert _persist_confidence(["oops", 0.9], 0) is None

    def test_non_indexable_scores_returns_none(self):
        assert _persist_confidence(None, 0) is None
        assert _persist_confidence(42, 0) is None


class TestExtractLinesParallelArrayMismatch:
    """FR-004 / R-013: parallel-array length mismatches preserve the line
    with `confidence=None` rather than silently dropping it."""

    def test_scores_shorter_than_texts(self):
        # rec_texts has 3 items; rec_scores has 2 → line 2 persists with None.
        fake = SimpleNamespace(
            rec_texts=["alpha", "beta", "gamma"],
            rec_boxes=[
                [[0, 0], [10, 0], [10, 10], [0, 10]],
                [[0, 10], [10, 10], [10, 20], [0, 20]],
                [[0, 20], [10, 20], [10, 30], [0, 30]],
            ],
            rec_scores=[0.9, 0.85],
        )
        lines = _extract_lines(fake, page_number=1, width=100, height=100)
        assert len(lines) == 3
        # One line has None (the one without a matching score); the other two
        # have the verbatim engine values.
        confidences = [ln["confidence"] for ln in lines]
        assert confidences.count(None) == 1
        assert any(c == pytest.approx(0.9) for c in confidences if c is not None)
        assert any(c == pytest.approx(0.85) for c in confidences if c is not None)

    def test_all_scores_missing(self):
        fake = SimpleNamespace(
            rec_texts=["alpha", "beta"],
            rec_boxes=[
                [[0, 0], [10, 0], [10, 10], [0, 10]],
                [[0, 10], [10, 10], [10, 20], [0, 20]],
            ],
            rec_scores=[],
        )
        lines = _extract_lines(fake, page_number=1, width=100, height=100)
        assert len(lines) == 2
        assert all(ln["confidence"] is None for ln in lines)

    def test_out_of_range_score_becomes_none(self):
        fake = SimpleNamespace(
            rec_texts=["alpha"],
            rec_boxes=[[[0, 0], [10, 0], [10, 10], [0, 10]]],
            rec_scores=[1.42],  # out-of-range on purpose
        )
        lines = _extract_lines(fake, page_number=1, width=100, height=100)
        assert len(lines) == 1
        assert lines[0]["confidence"] is None
