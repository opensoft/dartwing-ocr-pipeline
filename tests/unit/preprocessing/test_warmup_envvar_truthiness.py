"""Feature 016 (T023 / US3): truthiness-whitelist tests for the warmup
opt-in's `DARTWING_GPU_WARMUP` env var + CLI-flag-wins precedence.

CPU-safe: imports only `preprocessing.warmup_optin` which has zero GPU
dependencies (no paddle, no MIOpen, no numpy, no PIL, no pypdfium2).

Contracts exercised:
- ``research.md`` R-016.1: env-var truthiness whitelist
- ``contracts/cli-contract.md`` §1: activation surfaces + CLI-wins-over-env
- ``data-model.md`` §"Activation-surface state machine": 5-row truth table
"""
from __future__ import annotations

import pytest

from dartwing_ocr.preprocessing.warmup_optin import (
    is_gpu_lane,
    is_warmup_optin_set,
    warn_and_proceed_message,
)


# ---------------------------------------------------------------------------
# Truthiness whitelist (R-016.1 / data-model.md §"Activation-surface state machine")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "env_value",
    [
        "1",
        "true",
        "TRUE",       # case-insensitive
        "True",       # case-insensitive
        "yes",
        "YES",
        "  1  ",      # surrounding whitespace stripped
        "  true",
        "yes  ",
    ],
)
def test_truthy_env_values_resolve_to_optin(env_value: str) -> None:
    """Whitelist values (case-insensitive after strip) MUST resolve to
    True per cli-contract.md §1."""
    result = is_warmup_optin_set(False, env={"DARTWING_GPU_WARMUP": env_value})
    assert result is True, (
        f"env value {env_value!r} should resolve to True (whitelist match)"
    )


@pytest.mark.parametrize(
    "env_value",
    [
        "0",
        "false",
        "no",
        "FALSE",
        "off",         # NOT in whitelist
        "on",          # NOT in whitelist
        "enabled",     # NOT in whitelist
        "2",           # NOT in whitelist
        "",            # empty string
        "   ",         # whitespace only
        "y",           # NOT in whitelist (must be full word)
        "n",
        "1.0",         # not literal "1"
        "yes,please",
        "1 true",      # multi-token
    ],
)
def test_non_truthy_env_values_resolve_to_off(env_value: str) -> None:
    """Anything outside the whitelist (after strip + lower) MUST resolve to
    False — silently, NOT an error per cli-contract.md §1."""
    result = is_warmup_optin_set(False, env={"DARTWING_GPU_WARMUP": env_value})
    assert result is False, (
        f"env value {env_value!r} should resolve to False (not whitelisted, "
        "should NOT raise an error)"
    )


def test_unset_env_var_resolves_to_off() -> None:
    """An env dict without `DARTWING_GPU_WARMUP` resolves to False."""
    assert is_warmup_optin_set(False, env={}) is False
    assert is_warmup_optin_set(False, env={"OTHER": "1"}) is False


# ---------------------------------------------------------------------------
# CLI-wins-over-env precedence (R-016.1)
# ---------------------------------------------------------------------------


def test_cli_flag_true_wins_over_env_var_off() -> None:
    """CLI flag set explicitly wins over an off env var."""
    assert is_warmup_optin_set(True, env={"DARTWING_GPU_WARMUP": "0"}) is True


def test_cli_flag_true_wins_over_env_var_unset() -> None:
    """CLI flag set wins over unset env."""
    assert is_warmup_optin_set(True, env={}) is True


def test_cli_flag_false_yields_to_env_var_truthy() -> None:
    """CLI flag NOT set: env var truthiness governs."""
    assert is_warmup_optin_set(False, env={"DARTWING_GPU_WARMUP": "1"}) is True


def test_cli_flag_false_with_env_var_off_returns_off() -> None:
    """Both off → False."""
    assert is_warmup_optin_set(False, env={"DARTWING_GPU_WARMUP": "0"}) is False
    assert is_warmup_optin_set(False, env={}) is False


# ---------------------------------------------------------------------------
# Activation truth table (data-model.md §"Activation-surface state machine")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cli_flag,env_var,profile,expected_optin,expected_warmup_active",
    [
        # Row 1: opt-in absent → off everywhere
        (False, None, "ppstructurev3@cpu", False, False),
        (False, None, "ppstructurev3@gpu", False, False),
        # Row 2: env var set, GPU profile → opt-in on, warmup runs
        (False, "1", "ppstructurev3@gpu", True, True),
        # Row 3: env var set, CPU profile → opt-in on but warmup DOESN'T run
        # (warn-and-proceed instead)
        (False, "1", "ppstructurev3@cpu", True, False),
        # Row 4: CLI flag set, GPU profile → opt-in on, warmup runs
        (True, None, "ppstructurev3@gpu", True, True),
        # Row 5: CLI flag set, CPU profile → opt-in on but warn-and-proceed
        (True, None, "ppstructurev3@cpu", True, False),
    ],
)
def test_activation_truth_table_5_rows(
    cli_flag: bool,
    env_var: str | None,
    profile: str,
    expected_optin: bool,
    expected_warmup_active: bool,
) -> None:
    """The 5-row truth table from data-model.md §"Activation-surface state
    machine" — every (cli, env, profile) combination produces the
    expected opt-in detection AND the expected "warmup actually runs"
    decision (which requires both opt-in AND a GPU lane)."""
    env = {} if env_var is None else {"DARTWING_GPU_WARMUP": env_var}
    optin = is_warmup_optin_set(cli_flag, env=env)
    assert optin is expected_optin, (
        f"row (cli={cli_flag}, env={env_var}, profile={profile}): "
        f"expected optin={expected_optin}, got {optin}"
    )
    # Resolve profile string → preprocess lane (mirrors what cli.py does).
    if profile == "ppstructurev3@gpu":
        lane = "gpu0"
    else:
        lane = "cpu"
    warmup_active = optin and is_gpu_lane(lane)
    assert warmup_active is expected_warmup_active, (
        f"row (cli={cli_flag}, env={env_var}, profile={profile}): "
        f"expected warmup_active={expected_warmup_active}, got {warmup_active}"
    )


# ---------------------------------------------------------------------------
# Warn-and-proceed message stability (cli-contract.md §3)
# ---------------------------------------------------------------------------


def test_warn_and_proceed_message_contains_grep_literal() -> None:
    """The literal prefix `--gpu-warmup ignored:` is part of the cli-contract.md
    §3 contract — tests grep for this exact string. The message MUST include
    the active profile name in single quotes for operator triage."""
    msg = warn_and_proceed_message("ppstructurev3@cpu")
    assert "--gpu-warmup ignored:" in msg, (
        f"warn-and-proceed message MUST contain literal '--gpu-warmup ignored:'; "
        f"got {msg!r}"
    )
    assert "'ppstructurev3@cpu'" in msg


def test_warn_and_proceed_message_for_stub_adapter() -> None:
    """When the active profile is a stub adapter name (e.g., 'stub_v1'),
    the message includes that name verbatim."""
    msg = warn_and_proceed_message("stub_v1")
    assert "--gpu-warmup ignored:" in msg
    assert "'stub_v1'" in msg


# ---------------------------------------------------------------------------
# is_gpu_lane invariants (data-model.md §"Activation-surface state machine")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lane", ["gpu0", "gpu1", "gpu7", "gpu99"])
def test_is_gpu_lane_accepts_gpu_n(lane: str) -> None:
    assert is_gpu_lane(lane) is True


@pytest.mark.parametrize(
    "non_gpu",
    [
        "cpu",
        "stub",
        "stub_v1",
        "ppstructurev3@cpu",
        "gpu",       # no digit suffix
        "gpuX",      # non-digit suffix
        "GPU0",      # uppercase
        "",
    ],
)
def test_is_gpu_lane_rejects_non_gpu(non_gpu: str) -> None:
    assert is_gpu_lane(non_gpu) is False
