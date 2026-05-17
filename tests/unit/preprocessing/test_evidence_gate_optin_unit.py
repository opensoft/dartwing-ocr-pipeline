"""Feature 020 / T031 / R-020.1 / R-020.12 / MI-20 / MI-22: CPU-safe tests
for `preprocessing/evidence_gate_optin.py`."""

from __future__ import annotations

import io

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate_optin import (
    EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR,
    apply_skip_fallback_optin,
    evidence_gate_skip_fallback_warn_message,
    resolve_evidence_gate_skip_fallback,
)


def test_env_var_name() -> None:
    assert EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR == "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK"


def test_cli_true_wins_over_unset_env() -> None:
    assert resolve_evidence_gate_skip_fallback(True, env={}) is True


def test_cli_true_wins_over_falsy_env() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "false"}
        )
        is True
    )


def test_cli_true_wins_over_truthy_env() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "1"}
        )
        is True
    )


def test_cli_false_unset_env_returns_false() -> None:
    assert resolve_evidence_gate_skip_fallback(False, env={}) is False


@pytest.mark.parametrize("truthy", ["1", "true", "yes", "on"])
def test_cli_false_truthy_env_returns_true(truthy: str) -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": truthy}
        )
        is True
    )


@pytest.mark.parametrize("truthy", ["TRUE", "Yes", "On", "1", "tRuE"])
def test_cli_false_truthy_env_case_insensitive(truthy: str) -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": truthy}
        )
        is True
    )


def test_cli_false_truthy_env_strips_whitespace() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "  yes  "}
        )
        is True
    )


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off"])
def test_cli_false_falsy_env_returns_false(falsy: str) -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": falsy}
        )
        is False
    )


def test_cli_false_empty_string_env_returns_false() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": ""}
        )
        is False
    )


@pytest.mark.parametrize(
    "unrecognized",
    ["2", "enabled", "TruE!", "anything-else", "y", "n", "Y", "on1", "1.0", "maybe"],
)
def test_cli_false_unrecognized_env_raises_valueerror(unrecognized: str) -> None:
    with pytest.raises(ValueError, match=EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR):
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": unrecognized}
        )


def test_cli_true_with_unrecognized_env_still_returns_true() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "maybe"}
        )
        is True
    )


def test_warn_message_carries_grep_marker() -> None:
    msg = evidence_gate_skip_fallback_warn_message("ppstructurev3@cpu")
    assert "--evidence-gate-skip-fallback ignored:" in msg


def test_warn_message_carries_active_profile_name() -> None:
    msg = evidence_gate_skip_fallback_warn_message("ppstructurev3@cpu")
    assert "ppstructurev3@cpu" in msg


def test_warn_message_includes_expected_profile_marker() -> None:
    msg = evidence_gate_skip_fallback_warn_message("stub-default")
    assert "ppstructurev3@gpu" in msg


def test_apply_optin_false_returns_false_without_warn() -> None:
    stream = io.StringIO()
    result = apply_skip_fallback_optin(
        cli_value=False,
        is_gpu_profile=False,
        active_profile_name="ppstructurev3@cpu",
        env={},
        stream=stream,
    )
    assert result is False
    assert stream.getvalue() == ""


def test_apply_optin_true_on_gpu_returns_true_without_warn() -> None:
    stream = io.StringIO()
    result = apply_skip_fallback_optin(
        cli_value=True,
        is_gpu_profile=True,
        active_profile_name="ppstructurev3@gpu",
        env={},
        stream=stream,
    )
    assert result is True
    assert stream.getvalue() == ""


def test_apply_optin_true_on_non_gpu_warns_and_returns_false() -> None:
    stream = io.StringIO()
    result = apply_skip_fallback_optin(
        cli_value=True,
        is_gpu_profile=False,
        active_profile_name="ppstructurev3@cpu",
        env={},
        stream=stream,
    )
    assert result is False
    assert "--evidence-gate-skip-fallback ignored:" in stream.getvalue()
    assert "ppstructurev3@cpu" in stream.getvalue()


def test_apply_optin_unrecognized_env_propagates_valueerror() -> None:
    with pytest.raises(ValueError):
        apply_skip_fallback_optin(
            cli_value=False,
            is_gpu_profile=False,
            active_profile_name="ppstructurev3@cpu",
            env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "maybe"},
            stream=io.StringIO(),
        )
