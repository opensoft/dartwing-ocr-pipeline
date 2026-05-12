"""Feature 019 / T013 / R-019.1 / I-019.10 / I-019.14: CPU-safe tests for
`preprocessing/preprocess_strategy_optin.py`.
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.preprocess_strategy_optin import (
    PREPROCESS_STRATEGY_ENV_VAR,
    derive_run_summary_preprocess_strategy_id,
    is_gpu_lane,
    preprocess_strategy_warn_message,
    resolve_preprocess_strategy_value,
)


def test_env_var_name() -> None:
    assert PREPROCESS_STRATEGY_ENV_VAR == "LEDGERLINC_PREPROCESS_STRATEGY"


def test_cli_wins_when_env_unset() -> None:
    """CLI flag value returned when env is empty / not set (R-019.1)."""
    assert resolve_preprocess_strategy_value("ocr-only-v1", env={}) == "ocr-only-v1"


def test_env_fallback_when_cli_none() -> None:
    """Env-var value used when CLI flag is None (R-019.1)."""
    assert (
        resolve_preprocess_strategy_value(
            None, env={"LEDGERLINC_PREPROCESS_STRATEGY": "ocr-only-v1"}
        )
        == "ocr-only-v1"
    )


def test_cli_wins_over_env() -> None:
    """CLI flag wins when both set (R-019.1)."""
    assert (
        resolve_preprocess_strategy_value(
            "ppstructurev3",
            env={"LEDGERLINC_PREPROCESS_STRATEGY": "ocr-only-v1"},
        )
        == "ppstructurev3"
    )


def test_empty_string_env_treated_as_unset() -> None:
    """Empty-string env value counts as unset (matches feature 016/017/018)."""
    assert (
        resolve_preprocess_strategy_value(
            None, env={"LEDGERLINC_PREPROCESS_STRATEGY": ""}
        )
        is None
    )


def test_empty_string_cli_treated_as_unset() -> None:
    """Empty-string CLI value falls through to env (then None if env unset)."""
    assert resolve_preprocess_strategy_value("", env={}) is None


def test_env_value_passed_verbatim() -> None:
    """Env-var value handled verbatim — no .strip(), no lower() (R-019.1)."""
    assert (
        resolve_preprocess_strategy_value(
            None, env={"LEDGERLINC_PREPROCESS_STRATEGY": "  ocr-only-v1  "}
        )
        == "  ocr-only-v1  "
    )


def test_warn_message_carries_grep_marker() -> None:
    """The grep-able substring `--preprocess-strategy ignored:` MUST appear
    in the warn message per I-019.14."""
    msg = preprocess_strategy_warn_message("ppstructurev3@cpu")
    assert "--preprocess-strategy ignored:" in msg
    assert "ppstructurev3@cpu" in msg


def test_derive_gpu_with_threaded_value() -> None:
    """GPU lane + threaded value ⇒ value verbatim (R-019.1)."""
    assert (
        derive_run_summary_preprocess_strategy_id(
            threaded_preprocess_strategy="ocr-only-v1", preprocess_lane="gpu0"
        )
        == "ocr-only-v1"
    )


def test_derive_gpu_no_flag_defaults_to_ppstructurev3() -> None:
    """GPU lane + None ⇒ LEGACY_PREPROCESS_STRATEGY = "ppstructurev3" (R-019.4)."""
    assert (
        derive_run_summary_preprocess_strategy_id(
            threaded_preprocess_strategy=None, preprocess_lane="gpu0"
        )
        == "ppstructurev3"
    )


@pytest.mark.parametrize("threaded", [None, "ocr-only-v1", "ppstructurev3"])
def test_derive_cpu_lane_always_cpu_default(threaded: str | None) -> None:
    """CPU lane ⇒ "cpu-default" regardless of threaded value (R-019.3)."""
    assert (
        derive_run_summary_preprocess_strategy_id(
            threaded_preprocess_strategy=threaded, preprocess_lane="cpu"
        )
        == "cpu-default"
    )


def test_is_gpu_lane_reexport() -> None:
    """is_gpu_lane re-exported from warmup_optin for symmetry."""
    assert is_gpu_lane("gpu0") is True
    assert is_gpu_lane("cpu") is False
