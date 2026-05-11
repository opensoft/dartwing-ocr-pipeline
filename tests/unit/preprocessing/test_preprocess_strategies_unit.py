"""Feature 019 / T012 / R-019.2 / I-019.1: closed-vocabulary registry tests
for `preprocessing/preprocess_strategies.py`.

All tests are CPU-safe — no Paddle import, no GPU dependency.
"""

from __future__ import annotations

import sys

import pytest

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.preprocess_strategies import (
    OCR_ONLY_MIN_CONFIDENCE_MEAN,
    OCR_ONLY_MIN_TOKEN_COUNT,
    PREPROCESS_STRATEGIES,
    PreprocessStrategy,
    resolve_preprocess_strategy,
)


# ---------------------------------------------------------------------------
# R-019.2: closed vocabulary at landing (4 entries)
# ---------------------------------------------------------------------------


def test_registry_has_exactly_four_entries() -> None:
    """The closed vocabulary at landing is exactly:
    `ppstructurev3`, `ocr-only-v1`, `cpu-default`, `stub-default`."""
    assert set(PREPROCESS_STRATEGIES.keys()) == {
        "ppstructurev3",
        "ocr-only-v1",
        "cpu-default",
        "stub-default",
    }


def test_ppstructurev3_kind_is_ppstructurev3() -> None:
    """`ppstructurev3` is the layout-aware kind — dispatcher invokes
    PPStructureV3 on this kind."""
    s = PREPROCESS_STRATEGIES["ppstructurev3"]
    assert s.kind == "ppstructurev3"
    assert s.token_threshold is None
    assert s.confidence_threshold is None
    assert s.confidence_aggregator is None


def test_ocr_only_v1_kind_and_thresholds() -> None:
    """`ocr-only-v1` is the OCR-only kind with the R-019.5 / R-019.6
    threshold defaults (8 tokens, 0.60 confidence-mean) and the R-019.6
    arithmetic-mean aggregator."""
    s = PREPROCESS_STRATEGIES["ocr-only-v1"]
    assert s.kind == "ocr-only"
    assert s.token_threshold == 8
    assert s.token_threshold == OCR_ONLY_MIN_TOKEN_COUNT
    assert s.confidence_threshold == 0.60
    assert s.confidence_threshold == OCR_ONLY_MIN_CONFIDENCE_MEAN
    assert s.confidence_aggregator == "mean"


def test_cpu_and_stub_defaults_are_identity_kind() -> None:
    """`cpu-default` and `stub-default` are identity-kind presets —
    they're emitted as `preprocess_strategy_id` values on the CPU lane /
    stub adapter but the dispatcher never invokes them (warn-and-proceed
    nulls them upstream)."""
    for name in ("cpu-default", "stub-default"):
        s = PREPROCESS_STRATEGIES[name]
        assert s.kind == "identity"
        assert s.token_threshold is None
        assert s.confidence_threshold is None
        assert s.confidence_aggregator is None


# ---------------------------------------------------------------------------
# I-019.1 / R-019.12: resolve_preprocess_strategy fail-fast
# ---------------------------------------------------------------------------


def test_resolve_returns_registered_strategy() -> None:
    """Resolving a registered name returns the registry entry."""
    s = resolve_preprocess_strategy("ocr-only-v1")
    assert isinstance(s, PreprocessStrategy)
    assert s.name == "ocr-only-v1"
    assert s.kind == "ocr-only"


def test_resolve_raises_unknown_preset_error_on_typo() -> None:
    """`--preprocess-strategy ocr-only-v99` ⇒ UnknownPresetError(
    preset_axis="preprocess_strategy", ...) per R-019.12."""
    with pytest.raises(UnknownPresetError) as exc_info:
        resolve_preprocess_strategy("ocr-only-v99")
    err = exc_info.value
    assert err.preset_axis == "preprocess_strategy"
    assert err.preset_value == "ocr-only-v99"
    # valid_values contains all four registry keys
    assert set(err.valid_values) == {
        "ppstructurev3",
        "ocr-only-v1",
        "cpu-default",
        "stub-default",
    }
    # exit_code is 16 (reuses feature 017's UNKNOWN_PRESET per R-019.12)
    assert err.exit_code == 16


def test_resolve_raises_on_empty_string() -> None:
    """Empty string is not a valid preset name."""
    with pytest.raises(UnknownPresetError):
        resolve_preprocess_strategy("")


# ---------------------------------------------------------------------------
# I-019.10: CPU-import safety (no Paddle import at module load)
# ---------------------------------------------------------------------------


def test_module_load_is_paddle_import_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry module must import cleanly on a host without
    `paddleocr` / `paddle` — per I-019.10 / FR-014, CPU and stub paths
    MUST NOT import GPU-only OCR-only code at module-load time."""
    # Force a re-import with paddleocr blocked
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    monkeypatch.setitem(sys.modules, "paddle", None)
    # Reload the registry module — should still import cleanly
    import importlib

    import ledgerlinc_ocr.preprocessing.preprocess_strategies as mod

    reloaded = importlib.reload(mod)
    assert set(reloaded.PREPROCESS_STRATEGIES.keys()) == {
        "ppstructurev3",
        "ocr-only-v1",
        "cpu-default",
        "stub-default",
    }


# ---------------------------------------------------------------------------
# PreprocessStrategy immutability (frozen=True)
# ---------------------------------------------------------------------------


def test_preprocess_strategy_is_frozen() -> None:
    """PreprocessStrategy is a frozen dataclass — attempting to mutate
    raises FrozenInstanceError."""
    s = PREPROCESS_STRATEGIES["ppstructurev3"]
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
        s.name = "other"  # type: ignore[misc]
