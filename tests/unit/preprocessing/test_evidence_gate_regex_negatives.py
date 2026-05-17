"""Feature 020 review cleanup: regression tests for the BUSINESS_SUFFIX_RE
and TAX_ID_VAT_RE word-boundary semantics + the vendor-name-candidate
stop-word filter (B1).

These tests lock down behavior that the original PR did not assert and
that surfaced as likely-correctness bugs in review:

- B1: ``_count_vendor_name_candidates`` must filter punctuated header
  tokens (``INVOICE:``, ``Payment.``, ``Number,``) the same way it filters
  the bare uppercase forms — the prior ``tok.casefold().upper()`` lookup
  failed because the stop-word set holds bare uppercase words.
- B2: ``TAX_ID_VAT_RE`` must NOT match all-letter common header words
  (``INVOICE``, ``PAYMENT``, ``NUMBER``, ``BALANCE``, ``RECEIPT``) — the
  prior pattern ``[A-Z]{2}[A-Z0-9]{2,12}`` matched them and flipped
  ``tax_id_shaped_present=True`` on virtually every invoice header.
- M6: word-boundary discipline — neither regex should fire on tokens
  where the spec-relevant substring sits inside a longer word
  (``unincorporated``, ``incorporated-by-reference``, ``Co-operative``).
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    BUSINESS_SUFFIX_RE,
    TAX_ID_EIN_RE,
    TAX_ID_VAT_RE,
    _count_vendor_name_candidates,
    _tax_id_shaped_present,
)


# --- B1: stop-word filter must strip punctuation before lookup -------------


@pytest.mark.parametrize(
    "token",
    [
        "INVOICE:", "INVOICE.", "INVOICE,", "INVOICE;", "INVOICE!",
        "Payment.", "Payment,", "Payment:",
        "Number,", "Number:",
        "TOTAL:", "Total.", "Amount,", "Date:",
        "TAX:", "PAGE:", "From:", "To:",
        "DUE,",
    ],
)
def test_punctuated_stop_words_filtered(token: str) -> None:
    """B1: stop-word filter strips trailing punctuation before lookup so
    ``INVOICE:`` is filtered the same as bare ``INVOICE``."""
    assert _count_vendor_name_candidates([token]) == 0, (
        f"punctuated stop-word {token!r} leaked through vendor-name filter"
    )


def test_real_vendor_tokens_with_punctuation_still_counted() -> None:
    """B1 must not over-filter — real vendor tokens with punctuation
    (e.g. ``Acme,`` ``Widget.``) are still counted."""
    assert _count_vendor_name_candidates(["Acme,", "Widget."]) == 2


# --- B2: VAT regex must require at least one digit -------------------------


@pytest.mark.parametrize(
    "token",
    [
        # Common invoice header words that the prior pattern
        # `[A-Z]{2}[A-Z0-9]{2,12}` falsely matched.
        "INVOICE", "PAYMENT", "NUMBER", "BALANCE", "RECEIPT", "AMOUNT",
        "TOTAL", "SUBTOTAL", "QUANTITY", "DESCRIPTION",
        # All-letter all-caps that happens to look 2+2..12-shaped.
        "GBNOTAVAT", "DEABC", "FRBALANCE",
    ],
)
def test_all_letter_words_are_not_vat_shaped(token: str) -> None:
    """B2: an all-letter token (no digits anywhere) MUST NOT match
    TAX_ID_VAT_RE."""
    assert not TAX_ID_VAT_RE.search(token), (
        f"{token!r} falsely matched TAX_ID_VAT_RE — B2 regression"
    )
    assert not _tax_id_shaped_present([token]), (
        f"{token!r} falsely flipped tax_id_shaped_present"
    )


@pytest.mark.parametrize(
    "token",
    [
        "GB123456789", "DE12345", "FR12345678901",
        "IT12345678",  "ES12345678", "NL123456789B01",
        "GBABC123",     # mixed alphanumeric with digit — valid VAT shape
    ],
)
def test_real_vat_shapes_still_match(token: str) -> None:
    """B2: real VAT-shaped tokens with at least one digit must still
    match."""
    assert TAX_ID_VAT_RE.search(token), (
        f"{token!r} failed to match TAX_ID_VAT_RE — B2 over-corrected"
    )


def test_real_ein_still_matches() -> None:
    """EIN pattern is unchanged — still matches ``XX-XXXXXXX``."""
    assert TAX_ID_EIN_RE.search("12-3456789")
    assert TAX_ID_EIN_RE.search("EIN: 98-7654321")


# --- M6: word-boundary discipline ------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        # The substring `Incorporated` appears inside a longer word —
        # `\b` boundaries must prevent the match.
        "unincorporated",
        # A1 (post-review): `(?![\w-])` excludes a trailing hyphen so
        # the suffix never matches inside hyphenated compounds.
        "Inc-related", "Incorporated-by-reference", "Ltd-affiliate",
        "Corp-shell", "GmbH-AG", "LLC-subsidiary",
        # No business suffix anywhere.
        "regular", "text", "Header",
        # `Co-operative` lacks the literal `.` that `Co\.` requires.
        "Co-operative",
    ],
)
def test_business_suffix_word_boundary(token: str) -> None:
    """M6 + A1: BUSINESS_SUFFIX_RE only fires on a word-boundary-bounded
    suffix token; hyphenated compounds like ``Inc-related`` must NOT
    match."""
    assert not BUSINESS_SUFFIX_RE.search(token), (
        f"{token!r} falsely matched BUSINESS_SUFFIX_RE — word-boundary failure"
    )


@pytest.mark.parametrize(
    "token",
    [
        "Acme Inc.", "Globex Corp.", "Widget LLC", "Trading Ltd",
        "Software GmbH", "Holdings Limited", "Company Co.",
    ],
)
def test_business_suffix_real_matches(token: str) -> None:
    """M6: real suffix tokens still match — the negative tests don't
    over-correct."""
    assert BUSINESS_SUFFIX_RE.search(token), (
        f"{token!r} failed to match BUSINESS_SUFFIX_RE — over-corrected"
    )
