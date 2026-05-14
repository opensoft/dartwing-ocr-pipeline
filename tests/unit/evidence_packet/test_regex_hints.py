"""Unit tests for the four compiled regex patterns in ``regex_hints``."""
from __future__ import annotations

from dartwing_ocr.evidence_packet.regex_hints import (
    EIN_RE,
    EMAIL_RE,
    URL_RE,
    US_PHONE_RE,
    find_hints,
)


def _match_all(pattern, text):
    return [m.group(0) for m in pattern.finditer(text)]


def test_email_positive_and_negatives():
    assert _match_all(EMAIL_RE, "reach accounts@acme.com today") == ["accounts@acme.com"]
    assert _match_all(EMAIL_RE, "noreply+tag@sub.example.co.uk") == [
        "noreply+tag@sub.example.co.uk"
    ]
    assert _match_all(EMAIL_RE, "no-email-here") == []
    assert _match_all(EMAIL_RE, "@nope.com or bad@") == []


def test_url_positive_and_negatives():
    assert _match_all(URL_RE, "visit https://acme.com/pay") == ["https://acme.com/pay"]
    assert _match_all(URL_RE, "http://sub.example.org") == ["http://sub.example.org"]
    # IP-only URL excluded (TLD requires letters)
    assert _match_all(URL_RE, "http://192.168.1.1/admin") == []
    # Bare domain excluded
    assert _match_all(URL_RE, "go to acme.com for info") == []


def test_phone_positive_and_negatives():
    assert _match_all(US_PHONE_RE, "call (555) 123-4567 now") == ["(555) 123-4567"]
    assert _match_all(US_PHONE_RE, "dial 800-555-0100") == ["800-555-0100"]
    assert _match_all(US_PHONE_RE, "ID 123456789") == []


def test_ein_positive_and_negatives():
    assert _match_all(EIN_RE, "EIN 12-3456789 total") == ["12-3456789"]
    # ZIP+4: 12345-6789 — must NOT match (lookbehind rejects digit before)
    assert _match_all(EIN_RE, "ZIP 12345-6789") == []
    # Non-hyphenated 9-digit ID
    assert _match_all(EIN_RE, "SSN 123456789") == []


def test_find_hints_orders_ascending_and_preserves_duplicates():
    text = (
        "orders@example.com or (212) 555-0100\n"
        "also visit https://example.com plus orders@example.com again"
    )
    hits = find_hints(text)
    emails = [h[0] for h in hits["emails"]]
    starts_email = [h[1] for h in hits["emails"]]
    assert emails == ["orders@example.com", "orders@example.com"]
    assert starts_email == sorted(starts_email)
    assert [h[0] for h in hits["phones"]] == ["(212) 555-0100"]
    assert [h[0] for h in hits["websites"]] == ["https://example.com"]
    assert hits["tax_ids"] == []


def test_find_hints_returns_all_four_categories_even_when_empty():
    hits = find_hints("")
    assert set(hits.keys()) == {"emails", "websites", "phones", "tax_ids"}
    assert all(v == [] for v in hits.values())
