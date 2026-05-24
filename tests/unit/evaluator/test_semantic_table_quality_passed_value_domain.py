"""T055 — value-domain mapping for ``document_pass_fail.semantic_table_quality_passed``.

Covers MI-17 / Q20 / FR-025.

The writer (US3, ``src/dartwing_ocr/evaluator/document.py``) is the single
source of truth for the mapping ``status -> semantic_table_quality_passed``.
This test parametrizes over the four ``Q26`` enum status values and asserts
the writer produces:

    passed          -> True
    failed          -> False
    unevaluable     -> False
    not_applicable  -> None

with no other inputs to the mapping. The test pulls the mapping straight
from the writer module (``_SEMANTIC_PASSED_VALUE_DOMAIN`` +
``_semantic_quality_passed_value``) and from
``supports_semantic_quality_fields`` so the v1.3.0 contract-set pin is
also verified — the field is emitted only when ``contract_set_version``
is >= 1.3.0.

Pure unit-level: no filesystem, no Paddle, no network (MI-1).
"""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.document import (
    _SEMANTIC_PASSED_VALUE_DOMAIN,
    _semantic_quality_passed_value,
    supports_semantic_quality_fields,
)
from dartwing_ocr.evaluator.semantic_quality_report import StatusLiteral

# The closed Q26 status enum the mapping must accept verbatim. Pinned
# here as a tuple so a contributor cannot quietly drift the value domain
# without also updating this test.
_Q26_STATUS_ENUM: tuple[str, ...] = (
    "passed",
    "failed",
    "unevaluable",
    "not_applicable",
)

# Authoritative MI-17 mapping (pinned by spec.md Q20). Re-declared here
# (NOT imported) so the test catches a silent change to
# ``_SEMANTIC_PASSED_VALUE_DOMAIN`` in document.py — the comparison
# below is the regression net.
_EXPECTED_DOMAIN: dict[str, bool | None] = {
    "passed": True,
    "failed": False,
    "unevaluable": False,
    "not_applicable": None,
}


def test_value_domain_dict_matches_mi17_pin() -> None:
    """The writer's ``_SEMANTIC_PASSED_VALUE_DOMAIN`` dict matches the
    MI-17 / Q20 pin verbatim — same keys, same values, no extras."""
    assert _SEMANTIC_PASSED_VALUE_DOMAIN == _EXPECTED_DOMAIN


def test_value_domain_keys_are_exactly_the_q26_enum() -> None:
    """The mapping keys are exactly the four Q26 status values — no more,
    no fewer. Guards against drift of the closed status enum."""
    assert set(_SEMANTIC_PASSED_VALUE_DOMAIN.keys()) == set(_Q26_STATUS_ENUM)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("passed", True),
        ("failed", False),
        ("unevaluable", False),
        ("not_applicable", None),
    ],
    ids=["passed->True", "failed->False", "unevaluable->False", "not_applicable->None"],
)
def test_semantic_quality_passed_value_mapping(
    status: str, expected: bool | None
) -> None:
    """MI-17 / Q20 / FR-025: parametrize over the four ``Q26`` status enum
    values and assert the writer's status-to-passed mapping returns
    ``True`` / ``False`` / ``False`` / ``None`` respectively."""
    assert _semantic_quality_passed_value(status) is expected


def test_status_literal_alias_covers_full_q26_enum() -> None:
    """The ``StatusLiteral`` type alias in semantic_quality_report.py must
    enumerate exactly the four Q26 values — a cross-check that the
    semantic_quality_report and document writers agree on the status set."""
    # ``Literal`` exposes its args via ``typing.get_args``.
    import typing

    literal_args = set(typing.get_args(StatusLiteral))
    assert literal_args == set(_Q26_STATUS_ENUM)


@pytest.mark.parametrize("bad_status", ["PASSED", "Failed", "pass", "", "not-applicable"])
def test_unknown_status_raises_value_error(bad_status: str) -> None:
    """A status string outside the closed Q26 set raises ``ValueError`` at
    the writer boundary (MI-11 guard). The error message names the
    closed enum so the contributor can see what's allowed.

    Snake_case-only per Q26 / MI-11 — no capitalization variants accepted.
    """
    with pytest.raises(ValueError, match="Q26"):
        _semantic_quality_passed_value(bad_status)


def test_supports_semantic_quality_fields_v1_2_returns_false() -> None:
    """The v1.3.0-pinned helper returns ``False`` for v1.2.0 — the writer
    must not emit ``semantic_table_quality_passed`` on a v1.2.0-pinned
    evaluation_document.json (MI-22 byte-identity for vendor-identity
    flows)."""
    assert supports_semantic_quality_fields("1.2.0") is False


def test_supports_semantic_quality_fields_v1_3_returns_true() -> None:
    """v1.3.0 enables the additive semantic fields."""
    assert supports_semantic_quality_fields("1.3.0") is True


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0", False),
        ("1.1.0", False),
        ("1.2.0", False),
        ("1.3.0", True),
        ("1.4.0", True),
        ("2.0.0", True),
    ],
)
def test_supports_semantic_quality_fields_boundary(
    version: str, expected: bool
) -> None:
    """The semantic-field gate flips on at (major, minor) >= (1, 3); all
    lower versions return ``False``, all higher return ``True``."""
    assert supports_semantic_quality_fields(version) is expected
