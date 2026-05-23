"""Tests for the canonical scored-corpus folder allowlist (Q23 / MI-21 / SC-009 / R-022.15).

Validates that :data:`dartwing_ocr.validator.corpus_pattern.CANONICAL_FOLDER_PATTERN`
and :func:`is_scored_corpus_folder` enforce the closed difficulty vocabulary
(``easy`` / ``medium`` / ``hard``) and reject every non-matching basename
under the default-exclude rule that protects SC-009.
"""

from __future__ import annotations

import pytest

from dartwing_ocr.validator.corpus_pattern import (
    CANONICAL_FOLDER_PATTERN,
    is_scored_corpus_folder,
)


@pytest.mark.parametrize(
    "basename",
    [
        "inv_001_easy",
        "inv_001_medium",
        "inv_001_hard",
        "inv_010_easy",
        "inv_099_medium",
        "inv_999_hard",
        "inv_500_easy",
    ],
)
def test_canonical_basenames_match(basename: str) -> None:
    """Every basename in the closed difficulty vocabulary fully matches."""
    assert is_scored_corpus_folder(basename) is True
    assert CANONICAL_FOLDER_PATTERN.fullmatch(basename) is not None


@pytest.mark.parametrize(
    "basename",
    [
        # The named calibration sample from spec.md Edge Cases + Q23.
        "inv_024_hard_degraded_body",
        # Extra suffixes — default-exclude.
        "inv_001_extra",
        "inv_001_hard_extra",
        "inv_001_hard_v2",
        # Wrong digit count.
        "inv_1_hard",
        "inv_0001_hard",
        # Wrong delimiter or prefix.
        "INV_001_HARD",
        "inv-001-hard",
        "invoice_001_hard",
        # Wrong difficulty vocabulary (outside the closed set).
        "inv_001_trivial",
        "inv_001_easyish",
        "inv_001_HARD",
        # Missing components.
        "inv_001",
        "inv_001_",
        "001_hard",
        "_inv_001_hard",
        # Empty / whitespace.
        "",
        " ",
        " inv_001_hard",
        "inv_001_hard ",
        "inv_001_hard\n",
    ],
)
def test_non_canonical_basenames_rejected(basename: str) -> None:
    """Every non-matching basename is calibration material (SC-009 default-exclude)."""
    assert is_scored_corpus_folder(basename) is False
    assert CANONICAL_FOLDER_PATTERN.fullmatch(basename) is None


def test_pattern_compiled_once_at_module_load() -> None:
    """The canonical pattern is a module-level compiled re.Pattern, not a string."""
    import re

    assert isinstance(CANONICAL_FOLDER_PATTERN, re.Pattern)


def test_canonical_subset_of_identifier_safety_pattern() -> None:
    """The Q23 canonical fixture pattern is a strict subset of the Q-SEC-2/B safety pattern.

    Verifies the cross-feature consistency note in spec.md FR-003 and
    contracts/schema-amendments.md: every canonical fixture name must
    also pass the document_id safety pattern, so adding the safety
    pattern does not break existing fixture folder names.
    """
    import re

    identifier_safety_regex = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
    for basename in [
        "inv_001_easy",
        "inv_500_medium",
        "inv_999_hard",
    ]:
        assert CANONICAL_FOLDER_PATTERN.fullmatch(basename) is not None
        assert identifier_safety_regex.fullmatch(basename) is not None
