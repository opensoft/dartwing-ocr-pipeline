"""Unit tests for every normalization rule in research.md §§1–7."""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.normalize import (
    classify_company,
    classify_email,
    classify_phone,
    classify_postal,
    classify_state,
    classify_street,
    classify_tax_id,
    classify_value,
    classify_website,
    normalize_company,
    normalize_email,
    normalize_phone,
    normalize_postal,
    normalize_state,
    normalize_street,
    normalize_tax_id,
    normalize_website,
)
from dartwing_ocr.evaluator.scoring import ResultLabel


# --- §1 State abbreviation map ------------------------------------------------


def test_state_full_vs_abbrev_match() -> None:
    assert classify_state("California", "CA") is ResultLabel.MATCH
    assert classify_state("New York", "ny") is ResultLabel.MATCH


def test_state_mismatch() -> None:
    assert classify_state("California", "Oregon") is ResultLabel.MISMATCH


def test_state_territory_puerto_rico() -> None:
    assert classify_state("Puerto Rico", "PR") is ResultLabel.MATCH


def test_normalize_state_canonical_code() -> None:
    assert normalize_state("California") == "CA"
    assert normalize_state("ca") == "CA"


# --- §2 Phone: digits only + extension marker partial -------------------------


def test_phone_match_after_strip() -> None:
    assert classify_phone("(415) 555-0198", "4155550198") is ResultLabel.MATCH


def test_phone_partial_when_extension_dropped() -> None:
    assert (
        classify_phone("(415) 555-0198 ext. 203", "4155550198")
        is ResultLabel.PARTIAL_MATCH
    )


def test_phone_mismatch_entirely_different() -> None:
    assert classify_phone("4155550198", "9998887777") is ResultLabel.MISMATCH


def test_normalize_phone_digits_only() -> None:
    assert normalize_phone("+1 (415) 555-0198") == "14155550198"


# --- §3 Website --------------------------------------------------------------


def test_website_strips_scheme_www_and_trailing_slash() -> None:
    assert (
        classify_website("https://www.example.com/", "example.com") is ResultLabel.MATCH
    )


def test_website_preserves_path() -> None:
    assert (
        classify_website("http://example.com/vendor", "example.com/vendor")
        is ResultLabel.MATCH
    )


def test_website_strips_query_and_fragment() -> None:
    assert (
        classify_website("https://example.com?utm_source=x#top", "example.com")
        is ResultLabel.MATCH
    )


def test_website_mismatch_different_host() -> None:
    assert classify_website("example.com", "omega.com") is ResultLabel.MISMATCH


def test_normalize_website_basic() -> None:
    assert normalize_website("HTTPS://WWW.Example.COM/") == "example.com"


# --- §4 Postal code ----------------------------------------------------------


def test_postal_zip4_vs_zip_partial() -> None:
    assert classify_postal("94110-1234", "94110") is ResultLabel.PARTIAL_MATCH


def test_postal_exact_match() -> None:
    assert classify_postal("02110", "02110") is ResultLabel.MATCH


def test_postal_mismatch() -> None:
    assert classify_postal("94110", "94111") is ResultLabel.MISMATCH


def test_normalize_postal_trims() -> None:
    assert normalize_postal("  94110-1234 ") == "94110-1234"


# --- §5 Tax IDs --------------------------------------------------------------


def test_tax_id_match_after_strip() -> None:
    assert classify_tax_id("12-3456789", "123456789") is ResultLabel.MATCH


def test_tax_id_vat_prefix_preserved() -> None:
    assert classify_tax_id("DE 123456789", "DE123456789") is ResultLabel.MATCH


def test_tax_id_never_partial() -> None:
    # Off by one digit: MISMATCH, never PARTIAL_MATCH.
    assert classify_tax_id("12-3456789", "12-3456780") is ResultLabel.MISMATCH


def test_normalize_tax_id_strips_separators() -> None:
    assert normalize_tax_id("12-34.56 789") == "123456789"


# --- §6 Street ---------------------------------------------------------------


def test_street_suffix_normalized_match() -> None:
    assert classify_street("123 Main St", "123 Main Street") is ResultLabel.MATCH


def test_street_directional_normalized_match() -> None:
    assert (
        classify_street("500 N Maple Ave", "500 North Maple Avenue")
        is ResultLabel.MATCH
    )


def test_street_imperfect_normalization_partial() -> None:
    # Same number, same base words, but a qualifier added → PARTIAL_MATCH.
    assert (
        classify_street("123 Main Street Suite 400", "123 Main Street")
        is ResultLabel.PARTIAL_MATCH
    )


def test_street_different_number_mismatch() -> None:
    assert classify_street("123 Main St", "456 Main St") is ResultLabel.MISMATCH


def test_normalize_street_basic() -> None:
    assert normalize_street("500 N. Maple Ave.") == "500 north maple avenue"


# --- §7 Company name ---------------------------------------------------------


def test_company_suffix_strip_match() -> None:
    assert (
        classify_company("Acme Widgets Inc.", "Acme Widgets Incorporated")
        is ResultLabel.MATCH
    )


def test_company_token_subset_partial() -> None:
    assert (
        classify_company("Acme Widgets", "Acme Widgets Co. of California")
        is ResultLabel.PARTIAL_MATCH
    )


def test_company_punctuation_case_match() -> None:
    assert classify_company("Acme Widgets Inc.", "acme widgets  inc.") is ResultLabel.MATCH


def test_company_different_entity_mismatch() -> None:
    assert classify_company("Acme Widgets", "Omega Gadgets") is ResultLabel.MISMATCH


def test_normalize_company_strips_suffixes() -> None:
    assert normalize_company("Acme Widgets Incorporated") == "acme widgets"
    assert normalize_company("Acme Widgets, LLC") == "acme widgets"


# --- Email -------------------------------------------------------------------


def test_email_case_insensitive_match() -> None:
    assert (
        classify_email("Accounts@Example.COM", "accounts@example.com")
        is ResultLabel.MATCH
    )


def test_email_mismatch() -> None:
    assert classify_email("a@example.com", "b@example.com") is ResultLabel.MISMATCH


def test_normalize_email_lowercases_and_trims() -> None:
    assert normalize_email("  Foo@BAR.com ") == "foo@bar.com"


# --- Dispatcher --------------------------------------------------------------


@pytest.mark.parametrize(
    "field,expected,actual,label",
    [
        ("company_name.value", "Acme Widgets Inc.", "Acme Widgets Incorporated", ResultLabel.MATCH),
        ("address.state", "California", "CA", ResultLabel.MATCH),
        ("address.postal_code", "94110-1234", "94110", ResultLabel.PARTIAL_MATCH),
        ("phone", "(415) 555-0198 ext. 203", "4155550198", ResultLabel.PARTIAL_MATCH),
        ("website", "https://www.example.com/", "example.com", ResultLabel.MATCH),
        ("email", "A@B.com", "a@b.com", ResultLabel.MATCH),
        ("tax_ids.ein", "12-3456789", "123456789", ResultLabel.MATCH),
        ("company_name.present", True, True, ResultLabel.MATCH),
        ("manual_review_required", True, False, ResultLabel.MISMATCH),
    ],
)
def test_classify_value_dispatch(field: str, expected, actual, label: ResultLabel) -> None:
    assert classify_value(field, expected, actual) is label
