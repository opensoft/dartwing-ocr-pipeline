"""Feature 020 / T005 / FR-001 / R-020.3 / R-020.4 / MI-6 / SC-001:
CPU-safe per-signal unit tests for the five FR-001 signals.

**Cross-host claim (SC-001 second clause) — verified by-construction**:
signal computation is order-independent over detection boxes (uses ``sum()``
/ ``statistics.mean`` / regex match, no hash-set iteration ordering, no
float-comparison ordering dependency). NFKC normalization (T007) plus
pinned regex patterns (R-020.4) make the output environment-independent.
This file asserts byte-equality across two invocations within the same
process; the cross-host claim has no float-ordering risk to test against
since ``statistics.mean`` over a fixed input list is deterministic.
"""

from __future__ import annotations

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    FiveSignalSet,
    compute_five_signals,
    evaluate_evidence_gate,
)


def _doc_with_blocks(blocks: list[dict], page_height: int = 1000) -> dict:
    """Build a minimal preprocess_output dict with one page."""
    return {
        "pages": [
            {
                "page_number": 1,
                "width": 1000,
                "height": page_height,
                "rotation_detected": 0,
                "blocks": blocks,
                "raw_ocr_lines": [],
            }
        ]
    }


# --- vendor_name_candidate_count ------------------------------------------


def test_vendor_name_count_title_case() -> None:
    """Title-case tokens count as vendor-name candidates."""
    doc = _doc_with_blocks(
        [{"text": "Acme Widget", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    assert result.vendor_name_candidate_count == 2  # "Acme", "Widget"


def test_vendor_name_count_all_caps() -> None:
    """ALL-CAPS multi-char tokens count as vendor-name candidates.

    A5 expansion: business-entity suffix tokens (CORP, LLC, INC, ...)
    are now in the stop-word list because they are NOT vendor names —
    they are appended to vendor names. Fixture text uses two
    name-shaped tokens so the test still covers the ALL-CAPS case.
    """
    doc = _doc_with_blocks(
        [{"text": "ACME WIDGET", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    assert result.vendor_name_candidate_count == 2


def test_vendor_name_count_excludes_stop_words() -> None:
    """Stop-word tokens (INVOICE, TOTAL, etc.) are excluded even when
    title/upper case (R-020.3)."""
    doc = _doc_with_blocks(
        [
            {
                "text": "INVOICE TOTAL AMOUNT Acme",
                "confidence": 0.9,
                "bbox": [0, 0, 100, 100],
            }
        ]
    )
    result = compute_five_signals(doc)
    # Only "Acme" survives; INVOICE/TOTAL/AMOUNT are stop-words.
    assert result.vendor_name_candidate_count == 1


def test_vendor_name_count_excludes_pure_digits() -> None:
    """Pure-digit tokens (e.g., invoice numbers) do not count."""
    doc = _doc_with_blocks(
        [{"text": "Acme 12345 67890", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    assert result.vendor_name_candidate_count == 1


def test_vendor_name_count_excludes_single_char() -> None:
    """Single-character tokens (< 2 chars) do not count."""
    doc = _doc_with_blocks(
        [{"text": "A B Acme", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    assert result.vendor_name_candidate_count == 1


def test_vendor_name_case_folded_stop_word() -> None:
    """Stop-word comparison is case-folded (`invoice`, `Invoice` both excluded)."""
    doc = _doc_with_blocks(
        [{"text": "Invoice Acme invoice INVOICE", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    # All three "Invoice"-variants excluded; only "Acme" counts.
    assert result.vendor_name_candidate_count == 1


# --- header_band_token_density --------------------------------------------


def test_token_density_counts_all_whitespace_separated() -> None:
    """Density = total non-whitespace tokens in the band."""
    doc = _doc_with_blocks(
        [{"text": "one two three four five", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    assert result.header_band_token_density == 5


def test_token_density_empty_band_is_zero() -> None:
    """Empty band → density 0 (negative-level fallback)."""
    doc = _doc_with_blocks([])
    result = compute_five_signals(doc)
    assert result.header_band_token_density == 0


# --- ocr_detection_confidence_mean ----------------------------------------


def test_confidence_mean_arithmetic() -> None:
    """Mean is the arithmetic mean across in-band block confidences."""
    doc = _doc_with_blocks(
        [
            {"text": "foo", "confidence": 0.8, "bbox": [0, 0, 100, 100]},
            {"text": "bar", "confidence": 0.6, "bbox": [0, 50, 100, 150]},
        ]
    )
    result = compute_five_signals(doc)
    assert result.ocr_detection_confidence_mean == 0.7


def test_confidence_mean_empty_band_is_zero() -> None:
    """Empty band → mean 0.0 (negative-level fallback per data-model.md §2)."""
    doc = _doc_with_blocks([])
    result = compute_five_signals(doc)
    assert result.ocr_detection_confidence_mean == 0.0


def test_confidence_mean_clamps_outliers() -> None:
    """Out-of-range confidence is clamped to [0.0, 1.0] defensively."""
    doc = _doc_with_blocks(
        [{"text": "foo", "confidence": 1.5, "bbox": [0, 0, 100, 100]}]
    )
    result = compute_five_signals(doc)
    assert result.ocr_detection_confidence_mean == 1.0


# --- business_suffix_present ----------------------------------------------


def test_business_suffix_LLC() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme LLC", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_Inc() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme Inc", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_Incorporated() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme Incorporated", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_Ltd_Limited() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme Ltd Foo Limited", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_GmbH() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme GmbH", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_SA_variants() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme S.A. Other S.A.S.", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_Corp_Corporation_Co() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme Corp foo Corporation bar Co.", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is True


def test_business_suffix_case_insensitive() -> None:
    """Pattern uses ``(?i)`` flag — matches inc, INC, Inc."""
    for variant in ("inc.", "INC.", "Inc.", "iNc."):
        doc = _doc_with_blocks(
            [{"text": f"Acme {variant}", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
        )
        assert compute_five_signals(doc).business_suffix_present is True, variant


def test_business_suffix_absent() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme Widget", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).business_suffix_present is False


# --- tax_id_shaped_present ------------------------------------------------


def test_tax_id_EIN_shape() -> None:
    doc = _doc_with_blocks(
        [{"text": "EIN: 12-3456789", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).tax_id_shaped_present is True


def test_tax_id_VAT_shape() -> None:
    """EU VAT pattern: 2-letter country prefix + 2..12 alphanumerics
    with **at least one digit** (B2 / Phase 6 post-review tightening
    — see `data-model.md §6` for the literal regex)."""
    doc = _doc_with_blocks(
        [{"text": "VAT GB123456789", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).tax_id_shaped_present is True


def test_tax_id_EIN_case_sensitive_numbers() -> None:
    """EIN is numeric — no case variation. Lowercase letters between digits
    must NOT match."""
    doc = _doc_with_blocks(
        [{"text": "12-aaaaaaa", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).tax_id_shaped_present is False


def test_tax_id_VAT_case_sensitive_country() -> None:
    """VAT country prefix is uppercase per pattern. Lowercase prefix must
    NOT match."""
    doc = _doc_with_blocks(
        [{"text": "gb123456789", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).tax_id_shaped_present is False


def test_tax_id_absent() -> None:
    doc = _doc_with_blocks(
        [{"text": "Acme Widget Co.", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    assert compute_five_signals(doc).tax_id_shaped_present is False


# --- byte-identity invariant (MI-6 / SC-001) ------------------------------


def test_byte_identity_two_invocations_same_process() -> None:
    """Two invocations of ``evaluate_evidence_gate`` on the same input dict
    within the same process produce identical ``EvidenceGateResult``
    objects (MI-6).

    Cross-host byte-identity (SC-001 second clause) is verified
    by-construction — no float-ordering risk in ``statistics.mean`` over a
    fixed input list, deterministic regex matching, NFKC normalization.
    """
    doc = _doc_with_blocks(
        [
            {"text": "Acme Widget Corp.", "confidence": 0.95, "bbox": [0, 100, 900, 180]},
            {"text": "EIN: 12-3456789 some other tokens", "confidence": 0.90, "bbox": [0, 200, 900, 280]},
        ]
    )
    result_a = evaluate_evidence_gate(doc)
    result_b = evaluate_evidence_gate(doc)
    assert result_a == result_b
    assert result_a.signals == result_b.signals
    assert result_a.decision == result_b.decision
    assert result_a.evidence_gate_id == result_b.evidence_gate_id


def test_fiveSignalSet_field_types_match_data_model_spec() -> None:
    """FR-003 PII-safety closure — signal types are exactly
    int/int/float/bool/bool (no raw token strings leak in)."""
    doc = _doc_with_blocks(
        [{"text": "Acme", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
    )
    s = compute_five_signals(doc)
    assert isinstance(s, FiveSignalSet)
    assert isinstance(s.vendor_name_candidate_count, int)
    assert isinstance(s.header_band_token_density, int)
    assert isinstance(s.ocr_detection_confidence_mean, float)
    assert isinstance(s.business_suffix_present, bool)
    assert isinstance(s.tax_id_shaped_present, bool)
