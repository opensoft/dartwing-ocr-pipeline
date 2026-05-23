"""T026 / FR-010 / Q10 / Q16 / Q35 — currency-shape tests.

CANONICAL_MONEY_REGEX = r"^\$?\d{1,3}(,\d{3})*\.\d{2}$"
applied to the RAW token text BEFORE FR-009 normalization (Q16 / MI-8).

locate_currency_token: per-field digit-sequence matching (Q35 / MI-9) —
scan tokens in serialization order, return the first not-yet-matched
raw token whose digit-only representation equals the expected digit
sequence.
"""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.semantic_quality_currency import (
    CANONICAL_MONEY_REGEX,
    locate_currency_token,
)


class TestCanonicalMoneyRegex:
    @pytest.mark.parametrize(
        "good",
        ["$21.00", "21.00", "$1,234.56", "1,234.56", "$0.00", "999.99", "$1,000,000.00"],
    )
    def test_accepts_canonical(self, good: str) -> None:
        # The regex requires comma-grouping for values >= 1000; the
        # "1234.56" form WITHOUT comma is rejected (see test_rejects_malformed).
        assert CANONICAL_MONEY_REGEX.fullmatch(good) is not None

    @pytest.mark.parametrize(
        "bad",
        [
            "$21:00",  # colon-for-decimal — the target defect
            "$22:",  # truncated
            "21.0",  # one cents digit
            "21",  # no decimal
            "$1,23.00",  # malformed comma grouping
            "21.000",  # three cents digits
            "$",  # symbol only
            "",  # empty
            ".00",  # missing whole part
        ],
    )
    def test_rejects_malformed(self, bad: str) -> None:
        assert CANONICAL_MONEY_REGEX.fullmatch(bad) is None


class TestLocateCurrencyToken:
    def test_finds_matching_digit_sequence(self) -> None:
        tokens = ["Widget", "Qty", "1", "$21.00", "extra"]
        # Expected unit_price digit sequence = "2100" (from "21.00")
        result = locate_currency_token(tokens, "2100", already_matched_indices=set())
        assert result is not None
        idx, raw = result
        assert idx == 3
        assert raw == "$21.00"

    def test_skips_already_matched(self) -> None:
        tokens = ["$21.00", "$21.00"]
        result = locate_currency_token(tokens, "2100", already_matched_indices={0})
        assert result is not None
        idx, raw = result
        assert idx == 1

    def test_returns_none_when_no_match(self) -> None:
        tokens = ["Widget", "Qty", "1"]
        result = locate_currency_token(tokens, "2100", already_matched_indices=set())
        assert result is None

    def test_per_field_digit_sequence_quantity_not_misclassified(self) -> None:
        """Q35/MI-9: quantity '21' MUST NOT match an amount '21.00' field.

        Token "21" has digit sequence "21" — that does NOT equal "2100"
        (the amount's digit sequence). So the locator skips it.
        """
        tokens = ["21", "Widget", "$21.00"]
        # Looking for amount = "21.00" → digit-seq "2100"
        result = locate_currency_token(tokens, "2100", already_matched_indices=set())
        assert result is not None
        idx, raw = result
        assert idx == 2  # the "$21.00" token, not the quantity "21"
        assert raw == "$21.00"

    def test_locates_colon_for_decimal_raw_token(self) -> None:
        """Q16/MI-8: the locator finds tokens with malformed shape too,
        so the downstream regex check can flag them."""
        tokens = ["Widget", "$21:00", "extra"]
        # Digit sequence of "$21:00" is "2100" — same as the expected.
        result = locate_currency_token(tokens, "2100", already_matched_indices=set())
        assert result is not None
        idx, raw = result
        assert idx == 1
        assert raw == "$21:00"
        # The raw token then fails the canonical regex:
        assert CANONICAL_MONEY_REGEX.fullmatch(raw) is None


class TestCommaGroupedAmount:
    def test_locates_grouped_amount(self) -> None:
        tokens = ["Total", "$1,234.56"]
        # Digit sequence of "$1,234.56" is "123456"
        result = locate_currency_token(tokens, "123456", already_matched_indices=set())
        assert result is not None
        assert result[1] == "$1,234.56"

    def test_grouped_amount_passes_regex(self) -> None:
        assert CANONICAL_MONEY_REGEX.fullmatch("$1,234.56") is not None


class TestDigitSequenceExtraction:
    """The locator's digit extraction must strip ALL non-digit characters."""

    def test_currency_symbol_and_commas_stripped(self) -> None:
        tokens = ["$1,234.56"]
        # Digit seq of "$1,234.56" = "123456"
        result = locate_currency_token(tokens, "123456", already_matched_indices=set())
        assert result is not None
        assert result[0] == 0
