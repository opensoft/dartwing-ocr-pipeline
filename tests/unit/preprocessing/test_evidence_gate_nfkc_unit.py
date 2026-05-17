"""Feature 020 / T007 / R-020.3 / MI-9: NFKC Unicode normalization tests.

NFKC compatibility composition normalizes Unicode forms that would
otherwise tokenize differently across hosts/platforms. The gate applies
NFKC BEFORE whitespace tokenization so signal values are stable across
locales (Linux / macOS / Windows; en_US / ja_JP / etc.).
"""

from __future__ import annotations

from dartwing_ocr.preprocessing.evidence_gate import compute_five_signals


def _doc(text: str) -> dict:
    return {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": text, "confidence": 0.9, "bbox": [0, 0, 100, 100]}
                ],
                "raw_ocr_lines": [],
            }
        ]
    }


def test_fullwidth_alphabetic_normalized_to_ascii() -> None:
    """Fullwidth Latin letters (U+FF21..U+FF5A) normalize to ASCII letters
    under NFKC. 'Acme' written as fullwidth tokenizes the same as ASCII
    'Acme'."""
    # Fullwidth "Acme" — each char in the FFxx range.
    fullwidth = "Ａｃｍｅ"  # "Ａｃｍｅ"
    s = compute_five_signals(_doc(fullwidth))
    # After NFKC: "Acme" (title-case, alphabetic, not a stop-word, >= 2 chars)
    # → counts as a vendor-name candidate AND as a token.
    assert s.header_band_token_density == 1
    assert s.vendor_name_candidate_count == 1


def test_fullwidth_digit_normalized() -> None:
    """Fullwidth digits (U+FF10..U+FF19) normalize to ASCII digits.
    The EIN pattern ``\\d{2}-\\d{7}`` should match a fullwidth-EIN after
    normalization."""
    # Fullwidth digits for "12-3456789"
    fullwidth_ein = "１２-３４５６７８９"
    s = compute_five_signals(_doc(fullwidth_ein))
    # After NFKC: "12-3456789" matches TAX_ID_EIN_RE.
    assert s.tax_id_shaped_present is True


def test_combining_characters_normalized() -> None:
    """Combining characters (e.g., 'e' + combining acute U+0301 vs.
    precomposed 'é' U+00E9) normalize identically under NFKC."""
    decomposed = "Acmé"  # "Acme" with combining acute on 'e' (decomposed)
    s = compute_five_signals(_doc(decomposed))
    # NFKC collapses to "Acmé" — still title-case, still a candidate.
    assert s.vendor_name_candidate_count == 1


def test_ligature_normalized() -> None:
    """Ligatures (e.g., 'ﬁ' U+FB01) decompose under NFKC to 'fi'."""
    # "Acmeﬁed" (with ligature)
    ligatured = "Acmeﬁed"
    s = compute_five_signals(_doc(ligatured))
    # After NFKC: "Acmefied" — single token, title-case → 1 candidate.
    assert s.vendor_name_candidate_count == 1
    assert s.header_band_token_density == 1


def test_normalization_does_not_alter_ascii_input() -> None:
    """Pure ASCII input is unchanged by NFKC (idempotent on the ASCII
    subset)."""
    s = compute_five_signals(_doc("Acme Widget"))
    assert s.vendor_name_candidate_count == 2
    assert s.header_band_token_density == 2
