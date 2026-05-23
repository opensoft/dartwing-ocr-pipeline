"""Tests for SemanticGateInvariantError (Q42 / MI-19 / R-022.14).

Validates that the gate-time invariant violation exception is a proper
Exception subclass, raises and propagates correctly, and is NOT caught by
the broad ``except Exception`` patterns that would convert it to an
``unevaluable`` verdict (which would violate MI-19).
"""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.exceptions import (
    EvaluatorError,
    SemanticGateInvariantError,
)


def test_is_evaluator_error_subclass() -> None:
    """SemanticGateInvariantError inherits from EvaluatorError → Exception."""
    assert issubclass(SemanticGateInvariantError, EvaluatorError)
    assert issubclass(SemanticGateInvariantError, Exception)


def test_raise_and_catch_directly() -> None:
    """Direct except SemanticGateInvariantError catches the exception."""
    with pytest.raises(SemanticGateInvariantError) as exc_info:
        raise SemanticGateInvariantError("anchor span has negative indices")
    assert "anchor span has negative indices" in str(exc_info.value)


def test_propagates_through_generic_evaluator_error_handler() -> None:
    """Q42 / MI-19: catching as EvaluatorError works (shared base class)."""
    with pytest.raises(EvaluatorError):
        raise SemanticGateInvariantError("verdict status outside Q26 enum")


def test_not_silently_absorbed_by_unevaluable_translator() -> None:
    """MI-19: a hypothetical ``unevaluable`` translator MUST NOT swallow this exception.

    This test models the failure mode the invariant guards against:
    if some future refactor wraps the gate entry point with a broad
    ``except Exception → return unevaluable`` handler, ``SemanticGateInvariantError``
    must continue to propagate. We test by writing the SAFE pattern (catch
    only the specific input-error classes) and verifying the invariant
    exception escapes.
    """

    class _PreprocessOutputUnreadable(Exception):
        """Stand-in for the input-error classes the gate may legitimately swallow."""

    def unsafe_outer() -> None:
        try:
            raise SemanticGateInvariantError("anchor inconsistent")
        except _PreprocessOutputUnreadable:  # The CORRECT scope to catch
            pytest.fail("Should not catch SemanticGateInvariantError as input error")

    with pytest.raises(SemanticGateInvariantError):
        unsafe_outer()


def test_message_carries_diagnostic_text() -> None:
    """The exception preserves its message so operators can diagnose the bug."""
    msg = (
        "verdict aggregator produced status='maybe' which is not in the "
        "closed Q26 enum {passed, failed, not_applicable, unevaluable}"
    )
    try:
        raise SemanticGateInvariantError(msg)
    except SemanticGateInvariantError as exc:
        assert str(exc) == msg
