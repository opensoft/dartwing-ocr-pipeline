"""Feature 019 / T023 / R-019.5 / R-019.6 / R-019.7 / R-019.9 / I-019.3 /
I-019.9: CPU-safe tests for the FR-005 combined two-threshold eligibility
check in `preprocessing/ocr_only.py`.
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.ocr_only import (
    EligibilityVerdict,
    OcrOnlyLine,
    check_eligibility,
)


def _line(text: str, conf: float) -> OcrOnlyLine:
    return OcrOnlyLine(bbox=(0, 0, 100, 10), text=text, detector_confidence=conf)


# ---------------------------------------------------------------------------
# R-019.7 zero-detection short-circuit (I-019.3)
# ---------------------------------------------------------------------------


def test_empty_input_returns_insufficient() -> None:
    """Zero detections short-circuits to INSUFFICIENT BEFORE the mean
    computation (R-019.7 / I-019.3)."""
    v = check_eligibility([], token_threshold=8, confidence_threshold=0.6)
    assert v == EligibilityVerdict.INSUFFICIENT


# ---------------------------------------------------------------------------
# I-019.3 AND-semantics: both arms must hold for SUFFICIENT
# ---------------------------------------------------------------------------


def test_token_count_below_trips_even_with_high_confidence() -> None:
    """token_count < threshold ⇒ INSUFFICIENT regardless of high confidence."""
    # 1 line × 2 tokens = 2 tokens total, far below 8
    line = _line("Acme Corp", conf=0.99)
    v = check_eligibility(
        [line], token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.INSUFFICIENT


def test_low_confidence_trips_even_with_many_tokens() -> None:
    """mean_confidence < threshold ⇒ INSUFFICIENT regardless of high token count."""
    # 5 lines × 2 tokens = 10 tokens, but mean confidence = 0.3 < 0.6
    lines = [_line("Acme Corp", conf=0.3) for _ in range(5)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.INSUFFICIENT


def test_both_above_thresholds_yields_sufficient() -> None:
    """Both arms above thresholds ⇒ SUFFICIENT."""
    # 5 lines × 2 tokens = 10 ≥ 8; mean = 0.8 ≥ 0.6
    lines = [_line("Acme Corp", conf=0.8) for _ in range(5)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.SUFFICIENT


def test_both_below_thresholds_yields_insufficient() -> None:
    """Both arms below thresholds ⇒ INSUFFICIENT (defensive cross-check)."""
    lines = [_line("A", conf=0.3) for _ in range(2)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.INSUFFICIENT


# ---------------------------------------------------------------------------
# Inclusive-`>=` edges
# ---------------------------------------------------------------------------


def test_exact_threshold_token_count_is_sufficient() -> None:
    """token_count == threshold (inclusive `>=`) ⇒ SUFFICIENT when confidence holds."""
    # 4 lines × 2 tokens = 8 (exact threshold); mean = 0.9
    lines = [_line("A B", conf=0.9) for _ in range(4)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.SUFFICIENT


def test_exact_threshold_confidence_is_sufficient() -> None:
    """mean_confidence == threshold (inclusive `>=`) ⇒ SUFFICIENT when token count holds."""
    # 8 lines × 1 token = 8; mean = 0.6 exactly
    lines = [_line("A", conf=0.6) for _ in range(8)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.SUFFICIENT


def test_just_below_token_count_is_insufficient() -> None:
    """token_count = threshold - 1 ⇒ INSUFFICIENT."""
    # 7 lines × 1 token = 7 (1 below 8)
    lines = [_line("A", conf=0.9) for _ in range(7)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.INSUFFICIENT


# ---------------------------------------------------------------------------
# R-019.9 Unicode-whitespace tokenization
# ---------------------------------------------------------------------------


def test_unicode_whitespace_splits_tokens() -> None:
    """Python's `str.split()` honors Unicode whitespace (NBSP, etc.) per R-019.9."""
    # "foo bar" (NBSP) splits to 2 tokens
    lines = [_line("foo bar", conf=0.9) for _ in range(4)]
    # 4 lines × 2 tokens = 8 → at threshold
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.SUFFICIENT


def test_whitespace_only_line_contributes_zero_tokens() -> None:
    """A line containing only whitespace contributes 0 tokens."""
    # 8 lines × 0 tokens = 0 → INSUFFICIENT (token side)
    lines = [_line("   \t  ", conf=0.9) for _ in range(8)]
    v = check_eligibility(
        lines, token_threshold=8, confidence_threshold=0.6
    )
    assert v == EligibilityVerdict.INSUFFICIENT


# ---------------------------------------------------------------------------
# I-019.9: only 'mean' aggregator supported at landing
# ---------------------------------------------------------------------------


def test_unsupported_aggregator_raises() -> None:
    """confidence_aggregator must be 'mean' at landing (I-019.9)."""
    with pytest.raises(ValueError) as exc_info:
        check_eligibility(
            [_line("foo", conf=0.9)],
            token_threshold=8,
            confidence_threshold=0.6,
            confidence_aggregator="weighted_mean",
        )
    assert "weighted_mean" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Determinism: same input ⇒ same verdict
# ---------------------------------------------------------------------------


def test_determinism_repeat_input() -> None:
    """Two runs with the same input produce the same verdict (SC-012 / I-019.3)."""
    lines = [_line("Acme Corp", conf=0.7) for _ in range(5)]
    v1 = check_eligibility(lines, token_threshold=8, confidence_threshold=0.6)
    v2 = check_eligibility(lines, token_threshold=8, confidence_threshold=0.6)
    assert v1 == v2
