"""Feature 020 / T014 / R-020.6 / contracts/evidence-gate-rule.md:
parameterized truth-table test for the v1 decision-table body.

Covers all 32 truth-table rows (2^5 combinations of the five boolean
derivatives ``has_name``, ``has_density``, ``has_confidence``,
``has_suffix``, ``has_tax_id``). 3 rows fire ``sufficient``, 1 fires
``insufficient``, 28 fire ``borderline``.

Also asserts the inclusive-on-the-high-side comparison at the three
numeric threshold boundaries (count exactly 1, density exactly 8,
confidence exactly 0.70).
"""

from __future__ import annotations

from itertools import product

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    CONFIDENCE_THRESHOLD,
    DENSITY_THRESHOLD,
    EVIDENCE_GATES,
    FiveSignalSet,
    _v1_decide,
)


def _make_signals(
    *,
    has_name: bool,
    has_density: bool,
    has_confidence: bool,
    has_suffix: bool,
    has_tax_id: bool,
) -> FiveSignalSet:
    """Construct a FiveSignalSet matching the four boolean derivatives.

    Numeric values are chosen so the boolean threshold checks evaluate
    as expected (positive level just above threshold, negative level
    just below).
    """
    return FiveSignalSet(
        vendor_name_candidate_count=1 if has_name else 0,
        header_band_token_density=DENSITY_THRESHOLD if has_density else 0,
        ocr_detection_confidence_mean=CONFIDENCE_THRESHOLD if has_confidence else 0.0,
        business_suffix_present=has_suffix,
        tax_id_shaped_present=has_tax_id,
    )


# Build the canonical 32-row truth table per evidence-gate-rule.md.
# Returns (has_name, has_density, has_confidence, has_suffix, has_tax_id,
# expected_decision).
def _expected_decision(
    has_name: bool, has_density: bool, has_confidence: bool,
    has_suffix: bool, has_tax_id: bool,
) -> str:
    if (
        has_name and has_density and has_confidence
        and (has_suffix or has_tax_id)
    ):
        return "sufficient"
    if (
        not has_name and not has_density and not has_confidence
        and not has_suffix and not has_tax_id
    ):
        return "insufficient"
    return "borderline"


TRUTH_TABLE = [
    (*combo, _expected_decision(*combo))
    for combo in product([True, False], repeat=5)
]


@pytest.mark.parametrize(
    "has_name,has_density,has_confidence,has_suffix,has_tax_id,expected",
    TRUTH_TABLE,
)
def test_v1_decision_table_row(
    has_name: bool, has_density: bool, has_confidence: bool,
    has_suffix: bool, has_tax_id: bool, expected: str,
) -> None:
    """Every row in the v1 truth table maps to the documented decision."""
    signals = _make_signals(
        has_name=has_name, has_density=has_density,
        has_confidence=has_confidence, has_suffix=has_suffix,
        has_tax_id=has_tax_id,
    )
    assert _v1_decide(signals) == expected


def test_truth_table_row_counts() -> None:
    """3 rows → sufficient, 1 row → insufficient, 28 rows → borderline.
    Documented in contracts/evidence-gate-rule.md §Decision table."""
    counts = {"sufficient": 0, "borderline": 0, "insufficient": 0}
    for combo in product([True, False], repeat=5):
        counts[_expected_decision(*combo)] += 1
    assert counts == {"sufficient": 3, "insufficient": 1, "borderline": 28}


# --- Inclusive-on-the-high-side boundary assertions -----------------------


def test_density_boundary_exactly_8_qualifies_as_positive() -> None:
    """``header_band_token_density >= 8`` — exactly 8 is positive."""
    signals = FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=DENSITY_THRESHOLD,  # exactly 8
        ocr_detection_confidence_mean=0.70,
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    assert _v1_decide(signals) == "sufficient"


def test_density_boundary_7_qualifies_as_negative() -> None:
    """``header_band_token_density >= 8`` — 7 is negative."""
    signals = FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=DENSITY_THRESHOLD - 1,  # 7
        ocr_detection_confidence_mean=0.70,
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    # has_density = False → not sufficient (4-conjunct fails); other
    # signals positive → not insufficient → borderline.
    assert _v1_decide(signals) == "borderline"


def test_confidence_boundary_exactly_070_qualifies_as_positive() -> None:
    """``ocr_detection_confidence_mean >= 0.70`` — exactly 0.70 is positive."""
    signals = FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=DENSITY_THRESHOLD,
        ocr_detection_confidence_mean=CONFIDENCE_THRESHOLD,  # exactly 0.70
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    assert _v1_decide(signals) == "sufficient"


def test_confidence_boundary_069_qualifies_as_negative() -> None:
    signals = FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=DENSITY_THRESHOLD,
        ocr_detection_confidence_mean=CONFIDENCE_THRESHOLD - 0.01,  # 0.69
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    assert _v1_decide(signals) == "borderline"


def test_vendor_name_count_boundary_exactly_1_qualifies_as_positive() -> None:
    signals = FiveSignalSet(
        vendor_name_candidate_count=1,  # exactly 1
        header_band_token_density=DENSITY_THRESHOLD,
        ocr_detection_confidence_mean=0.70,
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    assert _v1_decide(signals) == "sufficient"


# --- Registry exposes _v1_decide consistently -----------------------------


def test_registry_v1_decide_matches_module_function() -> None:
    """``EVIDENCE_GATES['v1'].decide`` MUST be the same callable as the
    module-level ``_v1_decide`` (or behaviorally indistinguishable)."""
    s = FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=DENSITY_THRESHOLD,
        ocr_detection_confidence_mean=CONFIDENCE_THRESHOLD,
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    assert EVIDENCE_GATES["v1"].decide(s) == _v1_decide(s) == "sufficient"
