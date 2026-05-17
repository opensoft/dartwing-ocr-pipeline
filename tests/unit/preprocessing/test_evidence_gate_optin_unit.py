"""Feature 020 / T031 / R-020.1 / R-020.12 / MI-20 / MI-22: CPU-safe tests
for `preprocessing/evidence_gate_optin.py`.

Mirrors the structure of `tests/unit/preprocessing/test_preprocess_strategy_optin_unit.py`
(feature 019 / T013). Covers:

- Env-var name constant
- CLI > env precedence (R-020.1)
- Truthy env vocabulary {"1","true","yes","on"} case-insensitive
- Falsy / unrecognized / empty-string env → False
- Default OFF at landing (MI-20)
- Warn-message grep-able marker (MI-22)
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate_optin import (
    EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR,
    evidence_gate_skip_fallback_warn_message,
    resolve_evidence_gate_skip_fallback,
)


def test_env_var_name() -> None:
    """Env-var name is the canonical contract literal (R-020.1)."""
    assert EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR == "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK"


def test_cli_true_wins_over_unset_env() -> None:
    """CLI True returned when env is empty / not set (R-020.1)."""
    assert resolve_evidence_gate_skip_fallback(True, env={}) is True


def test_cli_true_wins_over_falsy_env() -> None:
    """CLI True returned when env is falsy (R-020.1)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "false"}
        )
        is True
    )


def test_cli_true_wins_over_truthy_env() -> None:
    """CLI True with truthy env → still True (cli wins) (R-020.1)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            True, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "1"}
        )
        is True
    )


def test_cli_false_unset_env_returns_false() -> None:
    """Default OFF at landing (MI-20 / FR-012). CLI False + unset env → False."""
    assert resolve_evidence_gate_skip_fallback(False, env={}) is False


def test_cli_none_unset_env_returns_false() -> None:
    """CLI None + unset env → False (default OFF — MI-20)."""
    assert resolve_evidence_gate_skip_fallback(None, env={}) is False


@pytest.mark.parametrize("truthy", ["1", "true", "yes", "on"])
def test_cli_false_truthy_env_returns_true(truthy: str) -> None:
    """CLI False + truthy env-var value → True (R-020.1 / cli-contract.md §1)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": truthy}
        )
        is True
    )


@pytest.mark.parametrize("truthy", ["TRUE", "Yes", "On", "1", "tRuE"])
def test_cli_false_truthy_env_case_insensitive(truthy: str) -> None:
    """Truthy vocabulary is case-insensitive after strip().lower() (R-020.1)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            None, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": truthy}
        )
        is True
    )


def test_cli_false_truthy_env_strips_whitespace() -> None:
    """Whitespace around the env value is stripped before comparison (R-020.1)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            None, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": "  yes  "}
        )
        is True
    )


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off"])
def test_cli_false_falsy_env_returns_false(falsy: str) -> None:
    """CLI False + falsy env-var value → False (R-020.1 — unrecognized non-truthy
    values are silently treated as False, cli-contract.md §1 silent-tolerance)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": falsy}
        )
        is False
    )


def test_cli_false_empty_string_env_returns_false() -> None:
    """Empty-string env value counts as unset (matches feature 016/017/018/019)."""
    assert (
        resolve_evidence_gate_skip_fallback(
            False, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": ""}
        )
        is False
    )


@pytest.mark.parametrize(
    "unrecognized",
    ["2", "enabled", "TruE!", "anything-else", " ", "y", "n", "Y", "True ", "on1"],
)
def test_cli_false_unrecognized_env_returns_false(unrecognized: str) -> None:
    """Unrecognized env values silently → False (R-020.1 / cli-contract.md §1).
    Notable: bare `y`/`n` are NOT in the vocabulary; full `yes`/`no` only.
    `True ` with trailing space DOES match (after .strip()); `Truthy ` doesn't
    (not in vocab). `on1` is rejected (vocab is exact tokens)."""
    # `True ` after strip().lower() is "true" → True. Exclude it from the
    # "unrecognized" set so the parametrize signal stays clean.
    if unrecognized.strip().lower() in {"1", "true", "yes", "on"}:
        pytest.skip(f"{unrecognized!r} normalizes into the truthy vocabulary")
    assert (
        resolve_evidence_gate_skip_fallback(
            None, env={"LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK": unrecognized}
        )
        is False
    )


def test_warn_message_carries_grep_marker() -> None:
    """The grep-able substring `--evidence-gate-skip-fallback ignored:` MUST
    appear in the warn message per MI-22 / R-020.12."""
    msg = evidence_gate_skip_fallback_warn_message("ppstructurev3@cpu")
    assert "--evidence-gate-skip-fallback ignored:" in msg


def test_warn_message_carries_active_profile_name() -> None:
    """The warn message interpolates the active profile name (mirrors
    features 017/018/019 warn-and-proceed messages)."""
    msg = evidence_gate_skip_fallback_warn_message("ppstructurev3@cpu")
    assert "ppstructurev3@cpu" in msg


def test_warn_message_includes_expected_profile_marker() -> None:
    """The warn message mentions the expected `ppstructurev3@gpu` profile
    so the operator understands what they should switch to."""
    msg = evidence_gate_skip_fallback_warn_message("stub-default")
    assert "ppstructurev3@gpu" in msg


def test_mi_20_default_off_invariant() -> None:
    """Feature 020 / T055 / MI-20 / FR-012 / FR-018: at landing, the
    opt-in default is OFF on every profile.

    This is the single focused invariant assertion T057 will flip when
    quality-gate evidence (FR-016 / R-020.14) supports promotion. Until
    then, ``resolve_evidence_gate_skip_fallback(cli_value=None,
    env=<empty>)`` MUST return ``False`` so legacy behavior is preserved
    byte-identically across all six profiles (SC-006 / SC-007).

    Flipping the default at T057 means replacing this assertion's
    expected value with ``True`` AND adding a regression test under
    ``tests/pipeline_tests/test_legacy_behavior_selectable_after_promotion.py``
    that exercises ``LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=0`` to
    confirm legacy non-suppression behavior is still selectable
    (FR-018).
    """
    assert resolve_evidence_gate_skip_fallback(cli_value=None, env={}) is False
