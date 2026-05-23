"""Tests for stable JSON serialization (Q34 / FR-014 / MI-16 / R-022.3).

Validates that :func:`dartwing_ocr.evaluator.stable_json.dump_stable` produces
byte-identical output for identical inputs and follows the Q34 convention
set: sorted keys at every nesting level, UTF-8 encoding, LF line endings,
trailing newline at EOF, no trailing whitespace, 6-dp ROUND_HALF_EVEN
floats emitted as JSON numbers (not strings), integers as JSON integers.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from dartwing_ocr.evaluator.stable_json import (
    SUPPORTING_EVIDENCE_FLOAT_PRECISION,
    dump_stable,
    round_half_even,
)


def test_sorted_keys_at_every_nesting_level(tmp_path: Path) -> None:
    """Q34: keys are sorted alphabetically at every nesting level."""
    obj = {
        "z_top": {"z_inner": 1, "a_inner": 2},
        "a_top": {"z_inner": 3, "a_inner": 4},
        "m_top": [{"z_item": 5, "a_item": 6}, {"z_item": 7, "a_item": 8}],
    }
    target = tmp_path / "sorted.json"
    dump_stable(obj, target)

    text = target.read_text(encoding="utf-8")
    a_top_pos = text.index('"a_top"')
    m_top_pos = text.index('"m_top"')
    z_top_pos = text.index('"z_top"')
    assert a_top_pos < m_top_pos < z_top_pos

    # Inner objects also sorted.
    a_inner_first = text.index('"a_inner"')
    z_inner_first = text.index('"z_inner"')
    assert a_inner_first < z_inner_first

    # Items inside the array also have sorted keys.
    a_item_first = text.index('"a_item"')
    z_item_first = text.index('"z_item"')
    assert a_item_first < z_item_first


def test_utf8_lf_trailing_newline_no_trailing_whitespace(tmp_path: Path) -> None:
    """Q34: UTF-8 encoding, LF line endings, exactly one trailing newline, no trailing whitespace."""
    obj = {"greeting": "héllo café"}  # non-ASCII to verify ensure_ascii=False
    target = tmp_path / "encoding.json"
    dump_stable(obj, target)

    raw = target.read_bytes()

    # UTF-8: the non-ASCII characters survive as multi-byte UTF-8, not as \uXXXX escapes.
    assert "héllo café".encode("utf-8") in raw

    # No CRLF.
    assert b"\r\n" not in raw
    assert b"\r" not in raw

    # Trailing newline.
    assert raw.endswith(b"\n")
    # Exactly one trailing newline (not two).
    assert not raw.endswith(b"\n\n")

    # No trailing whitespace on any line.
    text = raw.decode("utf-8")
    for line in text.split("\n"):
        assert line == line.rstrip(), (
            f"Line has trailing whitespace: {line!r}"
        )


def test_decimal_emitted_as_json_number_with_6_dp(tmp_path: Path) -> None:
    """Q34: Decimal values emit as fixed-precision JSON numbers, NOT strings."""
    obj = {
        "body_confidence_mean": Decimal("0.9712345678"),
        "body_confidence_min": Decimal("0.94"),
        "body_line_count": 24,
        "body_token_count": 187,
        "header_band_excluded": True,
    }
    target = tmp_path / "supporting_evidence.json"
    dump_stable(obj, target)

    text = target.read_text(encoding="utf-8")

    # Confidence values are JSON numbers, NOT quoted strings.
    # The Decimal "0.9712345678" rounds to 6 dp half-even → 0.971235.
    assert '"body_confidence_mean": 0.971235' in text
    assert '"body_confidence_mean": "0.971235"' not in text

    # Decimal("0.94") emits as a JSON number — 0.94 rounds to 0.94 (trailing zeros may be stripped by the float repr).
    assert '"body_confidence_min"' in text

    # Round-trip back through json.loads — confidence fields are numbers (not strings).
    parsed = json.loads(text)
    assert isinstance(parsed["body_confidence_mean"], (int, float))
    assert isinstance(parsed["body_confidence_min"], (int, float))
    assert isinstance(parsed["body_line_count"], int)
    assert isinstance(parsed["body_token_count"], int)
    assert isinstance(parsed["header_band_excluded"], bool)


@pytest.mark.parametrize(
    "input_value,expected",
    [
        # Banker's rounding (round-half-to-even).
        (Decimal("0.1234565"), 0.123456),  # last digit 5, prior digit 6 (even) -> stays
        (Decimal("0.1234575"), 0.123458),  # last digit 5, prior digit 7 (odd) -> rounds up
        # Plain rounding cases.
        (Decimal("0.9712345678"), 0.971235),
        (Decimal("0.5"), 0.5),
        (Decimal("0.000001"), 0.000001),
        # Float input also works via repr() round-trip.
        (0.5, 0.5),
        (1, 1.0),
        (0, 0.0),
    ],
)
def test_round_half_even(input_value: Decimal | float | int, expected: float) -> None:
    """round_half_even produces 6-dp ROUND_HALF_EVEN output as a float."""
    result = round_half_even(input_value)
    assert isinstance(result, float)
    assert result == expected, f"{input_value!r} -> {result} (expected {expected})"


def test_supporting_evidence_float_precision_constant() -> None:
    """Q34 / data-model §10 pins the precision at 6 decimal places."""
    assert SUPPORTING_EVIDENCE_FLOAT_PRECISION == 6


def test_byte_identical_across_two_consecutive_runs(tmp_path: Path) -> None:
    """SC-007 / MI-2: identical inputs produce byte-identical files."""
    obj = {
        "categories": ["malformed-currency-shape", "missing-required-content"],
        "supporting_evidence": {
            "body_confidence_mean": Decimal("0.97"),
            "body_confidence_min": Decimal("0.94"),
            "body_line_count": 24,
            "body_token_count": 187,
            "header_band_excluded": True,
        },
        "row_reasons": {
            "row-1": {"categories": ["malformed-currency-shape"], "reason": "test"},
        },
    }
    a = tmp_path / "run_a.json"
    b = tmp_path / "run_b.json"
    dump_stable(obj, a)
    dump_stable(obj, b)
    assert a.read_bytes() == b.read_bytes()


def test_zero_line_count_emits_floats_not_null(tmp_path: Path) -> None:
    """F3 resolution / R-022.12: when body_line_count is 0, both confidence fields emit as 0.0 (never null)."""
    obj = {
        "body_confidence_mean": Decimal("0.0"),
        "body_confidence_min": Decimal("0.0"),
        "body_line_count": 0,
        "body_token_count": 0,
        "header_band_excluded": False,
    }
    target = tmp_path / "empty_band.json"
    dump_stable(obj, target)

    text = target.read_text(encoding="utf-8")
    assert "null" not in text  # No null sneaks in for empty-band confidence.
    parsed = json.loads(text)
    # Use pytest.approx (Sonar python:S1244 — no float equality). The
    # round-tripped value is bit-exact 0.0; approx with default tolerance
    # accepts it and satisfies the rule. Per Sonar fix on PR #44.
    assert parsed["body_confidence_mean"] == pytest.approx(0.0)
    assert parsed["body_confidence_min"] == pytest.approx(0.0)
    assert isinstance(parsed["body_confidence_mean"], (int, float))
    assert isinstance(parsed["body_confidence_min"], (int, float))


def test_integer_counts_remain_integers(tmp_path: Path) -> None:
    """Q34: integer counts emit as JSON integers, not floats."""
    obj = {
        "semantic_passed_document_count": 5,
        "semantic_failed_document_count": 2,
        "semantic_table_quality_pass_rate": Decimal("0.714286"),
    }
    target = tmp_path / "metrics.json"
    dump_stable(obj, target)

    text = target.read_text(encoding="utf-8")
    # Integers serialize without a decimal point.
    assert '"semantic_passed_document_count": 5' in text
    assert '"semantic_passed_document_count": 5.0' not in text
    assert '"semantic_failed_document_count": 2' in text

    parsed = json.loads(text)
    assert isinstance(parsed["semantic_passed_document_count"], int)
    assert isinstance(parsed["semantic_failed_document_count"], int)
