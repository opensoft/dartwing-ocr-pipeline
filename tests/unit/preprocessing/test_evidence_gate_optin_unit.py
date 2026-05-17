"""Feature 020 / T031 / R-020.1 / R-020.12 / MI-20 / MI-22: CPU-safe tests
for `preprocessing/evidence_gate_optin.py`."""

from __future__ import annotations

import io

import pytest

from dartwing_ocr.preprocessing.evidence_gate_optin import (
    EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR,
    apply_skip_fallback_optin,
    evidence_gate_skip_fallback_warn_message,
    resolve_evidence_gate_skip_fallback,
)


def test_env_var_name() -> None:
    assert EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR == "DARTWING_EVIDENCE_GATE_SKIP_FALLBACK"


def test_cli_true_wins_over_unset_env() -> None:
    assert resolve_evidence_gate_skip_fallback(True, env={}) is True


def test_cli_true_wins_over_falsy_env() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": "false"}
        )
        is True
    )


def test_cli_true_wins_over_truthy_env() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": "1"}
        )
        is True
    )


def test_cli_false_unset_env_returns_false() -> None:
    assert resolve_evidence_gate_skip_fallback(False, env={}) is False


@pytest.mark.parametrize("truthy", ["1", "true", "yes", "on"])
def test_cli_false_truthy_env_returns_true(truthy: str) -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": truthy}
        )
        is True
    )


@pytest.mark.parametrize("truthy", ["TRUE", "Yes", "On", "1", "tRuE"])
def test_cli_false_truthy_env_case_insensitive(truthy: str) -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": truthy}
        )
        is True
    )


def test_cli_false_truthy_env_strips_whitespace() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": "  yes  "}
        )
        is True
    )


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off"])
def test_cli_false_falsy_env_returns_false(falsy: str) -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": falsy}
        )
        is False
    )


def test_cli_false_empty_string_env_returns_false() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": ""}
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
            False, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": unrecognized}
        )


def test_cli_true_with_unrecognized_env_still_returns_true() -> None:
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": "maybe"}
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


def test_mi_20_default_off_invariant() -> None:
    """Feature 020 / T055 / MI-20 / FR-012 / FR-018: at landing, the
    opt-in default is OFF on every profile.

    This is the single focused invariant assertion T057 will flip when
    quality-gate evidence (FR-016 / R-020.14) supports promotion. Until
    then, ``resolve_evidence_gate_skip_fallback(cli_value=None,
    env=<empty>)`` MUST return ``False`` so legacy behavior is preserved
    byte-identically (SC-006 / SC-007).

    The resolver is profile-blind (no profile argument), so off-once is
    off-everywhere by construction — one assertion suffices to pin MI-20
    across the entire profile matrix.

    The duplication with ``test_cli_none_unset_env_returns_false`` in
    this same file is INTENTIONAL — that test pins the resolver's
    mechanical behavior; this test names the MI-20 invariant explicitly
    so the promotion-flip site (T057) is locatable by test NAME (not
    line number, which drifts) in the test suite. Do not remove as a
    "duplicate" without updating T057's promotion procedure to point at
    the new pin.

    Flipping the default at T057 means replacing this assertion's
    expected value with ``True`` AND adding a regression test under
    ``tests/pipeline_tests/test_legacy_behavior_selectable_after_promotion.py``
    that exercises ``DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0`` to
    confirm legacy non-suppression behavior is still selectable
    (FR-018).
    """
    assert resolve_evidence_gate_skip_fallback(cli_value=None, env={}) is False


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
            env={"DARTWING_EVIDENCE_GATE_SKIP_FALLBACK": "maybe"},
            stream=io.StringIO(),
        )
