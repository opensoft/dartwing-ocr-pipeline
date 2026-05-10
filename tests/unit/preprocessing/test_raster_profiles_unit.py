"""Feature 018 (T011 / I-018.1 / I-018.2 / I-018.11 / R-018.12):
CPU-safe unit tests for the closed-vocabulary `RASTER_PROFILES` registry
and `resolve_raster_profile` resolver.

All tests are CPU-safe (no Paddle import, no GPU dependency).
"""

from __future__ import annotations

import sys

import pytest

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.raster_profiles import (
    RASTER_PROFILES,
    RasterProfile,
    resolve_raster_profile,
)
from ledgerlinc_ocr.preprocessing.version import DPI


# ---------------------------------------------------------------------------
# T011 (a) / I-018.1: closed vocabulary at landing
# ---------------------------------------------------------------------------


def test_raster_profiles_closed_vocabulary() -> None:
    """`RASTER_PROFILES` ships with exactly four entries at landing
    (R-018.2 / I-018.1)."""
    assert set(RASTER_PROFILES.keys()) == {
        "legacy",
        "reduced-v1",
        "cpu-default",
        "stub-default",
    }


# ---------------------------------------------------------------------------
# T011 (b) / I-018.11: legacy DPI single-source-of-truth
# ---------------------------------------------------------------------------


def test_legacy_dpi_reads_from_version_module() -> None:
    """`RASTER_PROFILES["legacy"].dpi` MUST be exactly
    `preprocessing.version.DPI` at module-load time (I-018.11). If
    `version.DPI` ever changes, `legacy` follows it without code change
    in `raster_profiles.py`."""
    assert RASTER_PROFILES["legacy"].dpi == DPI


# ---------------------------------------------------------------------------
# T011 (c) / R-018.3: reduced-v1 DPI value pinned at 200
# ---------------------------------------------------------------------------


def test_reduced_v1_dpi_is_200() -> None:
    """`reduced-v1` rasterizes at 200 DPI per R-018.3 (chosen as a
    safety-comfortable reduction from 300 DPI that still keeps a margin
    above the ~150 DPI floor for PaddleOCR detection on small text)."""
    assert RASTER_PROFILES["reduced-v1"].dpi == 200


# ---------------------------------------------------------------------------
# T011 (d) / R-018.2: CPU and stub identity-preset DPIs
# ---------------------------------------------------------------------------


def test_identity_preset_dpis_are_300() -> None:
    """CPU-default and stub-default identity presets carry `dpi = 300`
    (matching the CPU rasterizer's existing module-level `DPI` constant
    and the stub adapter, which never actually rasterizes). Identity
    presets exist for the run_summary identifier surface (FR-011), not
    to mutate the CPU rasterizer (FR-015 / I-018.2)."""
    assert RASTER_PROFILES["cpu-default"].dpi == 300
    assert RASTER_PROFILES["stub-default"].dpi == 300


# ---------------------------------------------------------------------------
# T011 (e): resolver returns the registered preset
# ---------------------------------------------------------------------------


def test_resolve_raster_profile_returns_preset() -> None:
    """`resolve_raster_profile("legacy")` returns the `legacy` entry."""
    p = resolve_raster_profile("legacy")
    assert isinstance(p, RasterProfile)
    assert p.name == "legacy"
    assert p.dpi == DPI


@pytest.mark.parametrize(
    "name",
    ["legacy", "reduced-v1", "cpu-default", "stub-default"],
)
def test_resolve_raster_profile_for_every_registered_name(name: str) -> None:
    """Every registered name resolves to a `RasterProfile` whose `name`
    field matches the registry key."""
    p = resolve_raster_profile(name)
    assert isinstance(p, RasterProfile)
    assert p.name == name


# ---------------------------------------------------------------------------
# T011 (f) / I-018.1 / R-018.12: unknown value raises UnknownPresetError
# ---------------------------------------------------------------------------


def test_unknown_raster_profile_raises_unknown_preset_error() -> None:
    """`resolve_raster_profile("reduced-v99")` raises `UnknownPresetError`
    with `preset_axis="raster_profile"` and `valid_values` containing
    all four registered names (R-018.12 / I-018.1)."""
    with pytest.raises(UnknownPresetError) as excinfo:
        resolve_raster_profile("reduced-v99")
    err = excinfo.value
    assert err.preset_axis == "raster_profile"
    assert err.preset_value == "reduced-v99"
    assert set(err.valid_values) == {
        "legacy",
        "reduced-v1",
        "cpu-default",
        "stub-default",
    }
    # `exit_code` class attribute is reused from feature 017
    # (R-018.12 — additive widening of `preset_axis: Literal[…]`,
    # not a new exception class).
    assert err.exit_code == 16


# ---------------------------------------------------------------------------
# T011 (g) / I-018.2: module-load is CPU-safe (no Paddle import)
# ---------------------------------------------------------------------------


def test_raster_profiles_module_imports_without_paddle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host without Paddle GPU MUST be able to
    `import ledgerlinc_ocr.preprocessing.raster_profiles` cleanly
    (FR-015 / I-018.2). Poison `paddleocr` and `paddle` in
    `sys.modules` and verify the registry module reloads successfully
    without touching either dependency."""
    import importlib

    # Drop any cached references first
    for mod_name in [
        "ledgerlinc_ocr.preprocessing.raster_profiles",
        "paddleocr",
        "paddle",
    ]:
        sys.modules.pop(mod_name, None)
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    monkeypatch.setitem(sys.modules, "paddle", None)
    # Re-import — should succeed without touching paddleocr / paddle
    mod = importlib.import_module(
        "ledgerlinc_ocr.preprocessing.raster_profiles"
    )
    assert hasattr(mod, "RASTER_PROFILES")
    assert "legacy" in mod.RASTER_PROFILES
