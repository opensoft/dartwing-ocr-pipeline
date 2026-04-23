"""Unit tests for the FR-020 warning vocabulary + ordering helpers (T027)."""

import pytest

from ledgerlinc_ocr.preprocessing.warnings import (
    STATUS_DOWNGRADING,
    WARNING_CATEGORIES,
    build_warning,
    sort_warnings,
    warning_sort_key,
)


def test_vocabulary_is_exactly_the_four_fr020_tokens():
    assert WARNING_CATEGORIES == [
        "silent_empty_layout",
        "silent_empty_ocr",
        "suspicious_single_block",
        "unknown_layout_label",
    ]


def test_status_downgrading_is_the_silent_empty_pair():
    assert STATUS_DOWNGRADING == frozenset(
        {"silent_empty_layout", "silent_empty_ocr"}
    )


def test_build_warning_format_matches_fr020_prefix():
    s = build_warning(3, "silent_empty_layout", "OCR produced 5 lines but layout returned zero blocks")
    assert s == "page 3: [silent_empty_layout] OCR produced 5 lines but layout returned zero blocks"


def test_build_warning_rejects_unknown_category():
    with pytest.raises(ValueError, match="unknown warning category"):
        build_warning(1, "not_a_real_token", "detail")


def test_warning_sort_key_orders_by_page_then_vocabulary_lexical():
    """Outer key = page_number; inner key = vocabulary lexical order within a page."""
    warnings = [
        build_warning(2, "unknown_layout_label", "label=foo"),
        build_warning(1, "silent_empty_ocr", "OCR returned zero lines despite 2 text-type blocks"),
        build_warning(1, "silent_empty_layout", "OCR produced 1 lines but layout returned zero blocks"),
        build_warning(2, "suspicious_single_block", "single block covers 3 OCR lines"),
    ]
    sorted_out = sort_warnings(warnings)
    assert sorted_out == [
        build_warning(1, "silent_empty_layout", "OCR produced 1 lines but layout returned zero blocks"),
        build_warning(1, "silent_empty_ocr", "OCR returned zero lines despite 2 text-type blocks"),
        build_warning(2, "suspicious_single_block", "single block covers 3 OCR lines"),
        build_warning(2, "unknown_layout_label", "label=foo"),
    ]


def test_sort_places_page_freeform_after_categorized_within_page():
    """Runtime-error messages in the `page N:` format sort after categorized on their page."""
    warnings = [
        "page 1: layout extraction failed: RuntimeError: boom",
        build_warning(1, "silent_empty_layout", "OCR produced 2 lines but layout returned zero blocks"),
        build_warning(1, "unknown_layout_label", "label=foo"),
    ]
    sorted_out = sort_warnings(warnings)
    # Categorized pair first (lexical), free-form last on page 1.
    assert sorted_out[0].startswith("page 1: [silent_empty_layout]")
    assert sorted_out[1].startswith("page 1: [unknown_layout_label]")
    assert sorted_out[2] == "page 1: layout extraction failed: RuntimeError: boom"


def test_sort_places_aggregate_warnings_last_in_document():
    """Non-page-scoped aggregate warnings sort after all page-scoped ones."""
    warnings = [
        "ingestion_sources.paddleocr_vl: failure (all pages failed)",
        build_warning(2, "silent_empty_layout", "OCR produced 1 lines but layout returned zero blocks"),
        build_warning(1, "silent_empty_ocr", "OCR returned zero lines despite 1 text-type blocks"),
    ]
    sorted_out = sort_warnings(warnings)
    assert sorted_out[0].startswith("page 1: [silent_empty_ocr]")
    assert sorted_out[1].startswith("page 2: [silent_empty_layout]")
    assert sorted_out[2] == "ingestion_sources.paddleocr_vl: failure (all pages failed)"


def test_sort_preserves_insertion_order_on_same_page_and_category():
    """FR-020 step 3 tie-break: equal (page, category) retains emission order."""
    w1 = build_warning(1, "unknown_layout_label", "label=alpha")
    w2 = build_warning(1, "unknown_layout_label", "label=beta")
    w3 = build_warning(1, "unknown_layout_label", "label=gamma")
    sorted_out = sort_warnings([w2, w1, w3])
    # Stable sort preserves the input order when keys tie.
    assert sorted_out == [w2, w1, w3]


def test_warning_sort_key_shape():
    """Return shape is a 3-tuple; callers may rely on its ordering semantics."""
    key = warning_sort_key(build_warning(5, "silent_empty_layout", "x"))
    assert isinstance(key, tuple) and len(key) == 3
    assert key[0] == 5
