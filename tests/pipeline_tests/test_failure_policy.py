"""Unit tests for --on-failure parsing and per-mode defaults.

Covers Spec FR-028; Research R-008 / R-010.
"""
from __future__ import annotations

import pytest

from dartwing_ocr.pipeline.failure_policy import (
    ACCEPTED_MODES,
    FailurePolicy,
    FailurePolicyError,
    parse_on_failure,
)


def test_warm_corpus_default_is_continue():
    p = parse_on_failure(None, warm_corpus=True)
    assert p.mode == "continue"
    assert p.fail_fast is False


def test_cold_default_is_fail_fast():
    p = parse_on_failure(None, warm_corpus=False)
    assert p.mode == "fail-fast"
    assert p.fail_fast is True


@pytest.mark.parametrize("raw", ["continue", "Continue", "CONTINUE", "  continue  "])
def test_continue_parsed_case_insensitive_and_whitespace_trimmed(raw):
    assert parse_on_failure(raw, warm_corpus=True).mode == "continue"


@pytest.mark.parametrize("raw", ["fail-fast", "Fail-Fast", "FAIL-FAST"])
def test_fail_fast_parsed_case_insensitive(raw):
    assert parse_on_failure(raw, warm_corpus=True).mode == "fail-fast"


@pytest.mark.parametrize("raw", ["fast", "stop", "abort", "yes", "no"])
def test_unknown_modes_rejected(raw):
    with pytest.raises(FailurePolicyError):
        parse_on_failure(raw, warm_corpus=True)


def test_accepted_modes_constant_matches_implementation():
    assert ACCEPTED_MODES == ("continue", "fail-fast")


def test_explicit_value_overrides_default_in_cold_mode():
    """Cold mode is semantically a no-op for --on-failure but the policy still records the parse."""
    p = parse_on_failure("continue", warm_corpus=False)
    assert p.mode == "continue"


def test_argparse_does_not_block_case_insensitive_input():
    """Copilot review item 11: --on-failure must reach parse_on_failure
    regardless of casing/whitespace, so tolerant parsing applies.
    """
    from dartwing_ocr.pipeline.cli import _build_parser

    parser = _build_parser()
    # ``Continue`` (capitalized) is rejected by the old argparse choices
    # but is valid case-insensitive input for parse_on_failure.
    args = parser.parse_args(["run", "--input", "/x", "--on-failure", "Continue"])
    assert args.on_failure == "Continue"
    # parse_on_failure normalizes it.
    p = parse_on_failure(args.on_failure, warm_corpus=True)
    assert p.mode == "continue"

    # Same for FAIL-FAST.
    args = parser.parse_args(["run", "--input", "/x", "--on-failure", "FAIL-FAST"])
    assert args.on_failure == "FAIL-FAST"
    assert parse_on_failure(args.on_failure, warm_corpus=True).mode == "fail-fast"


def test_failure_policy_is_immutable():
    p = FailurePolicy(mode="continue")
    with pytest.raises(Exception):  # frozen dataclass -> FrozenInstanceError
        p.mode = "fail-fast"  # type: ignore[misc]
