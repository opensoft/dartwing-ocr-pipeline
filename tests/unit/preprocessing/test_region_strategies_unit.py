"""Feature 018 (T022 / I-018.1 / I-018.2 / I-018.4 / R-018.5 / R-018.12):
CPU-safe unit tests for the closed-vocabulary `REGION_STRATEGIES`
registry, `resolve_region_strategy` resolver, and the `header-first-v1`
deterministic page-targeting rule.

Trigger-fired predicate tests live in `test_region_strategies_trigger.py`
(T023). Coordinate-translation tests live in
`test_coordinate_translation.py` (T024).

All tests are CPU-safe (no Paddle import, no GPU dependency).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.region_strategies import (
    BBox,
    REGION_STRATEGIES,
    RegionStrategy,
    resolve_region_strategy,
)


# ---------------------------------------------------------------------------
# Synthetic PDF doc / page stubs (no pypdfium2 dependency in these tests)
# ---------------------------------------------------------------------------


@dataclass
class _StubPage:
    width_pt: float
    height_pt: float

    def get_size(self) -> tuple[float, float]:
        return self.width_pt, self.height_pt

    def get_rotation(self) -> int:
        return 0

    def close(self) -> None:
        pass


@dataclass
class _StubDoc:
    pages: list[_StubPage]

    def get_page(self, idx: int) -> _StubPage:
        return self.pages[idx]

    def __len__(self) -> int:
        return len(self.pages)

    def __getitem__(self, idx: int) -> _StubPage:
        return self.pages[idx]

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# T022 (a) / I-018.1: closed vocabulary at landing
# ---------------------------------------------------------------------------


def test_region_strategies_closed_vocabulary() -> None:
    """`REGION_STRATEGIES` ships with exactly four entries at landing
    (R-018.4 / I-018.1)."""
    assert set(REGION_STRATEGIES.keys()) == {
        "full-page",
        "header-first-v1",
        "cpu-default",
        "stub-default",
    }


# ---------------------------------------------------------------------------
# T022 (b): resolver returns the registered preset
# ---------------------------------------------------------------------------


def test_resolve_region_strategy_returns_preset() -> None:
    """`resolve_region_strategy("full-page")` returns the `full-page`
    entry."""
    s = resolve_region_strategy("full-page")
    assert isinstance(s, RegionStrategy)
    assert s.name == "full-page"


@pytest.mark.parametrize(
    "name",
    ["full-page", "header-first-v1", "cpu-default", "stub-default"],
)
def test_resolve_region_strategy_for_every_registered_name(name: str) -> None:
    """Every registered name resolves to a `RegionStrategy` whose
    `name` field matches the registry key."""
    s = resolve_region_strategy(name)
    assert isinstance(s, RegionStrategy)
    assert s.name == name


# ---------------------------------------------------------------------------
# T022 (c) / I-018.1 / R-018.12: unknown value raises UnknownPresetError
# ---------------------------------------------------------------------------


def test_unknown_region_strategy_raises_unknown_preset_error() -> None:
    """`resolve_region_strategy("header-first-v99")` raises
    `UnknownPresetError` with `preset_axis="region_strategy"` and
    `valid_values` of length 4 (R-018.12)."""
    with pytest.raises(UnknownPresetError) as excinfo:
        resolve_region_strategy("header-first-v99")
    err = excinfo.value
    assert err.preset_axis == "region_strategy"
    assert err.preset_value == "header-first-v99"
    assert set(err.valid_values) == {
        "full-page",
        "header-first-v1",
        "cpu-default",
        "stub-default",
    }
    assert err.exit_code == 16


# ---------------------------------------------------------------------------
# T022 (d) / I-018.4 / R-018.5: header-first-v1 page targeting
# ---------------------------------------------------------------------------


def test_header_first_v1_page_targeting_page_0_returns_top_band() -> None:
    """`header-first-v1.page_targeting(doc, 0)` returns
    `BBox(0, 0, width_pt, 0.30 * height_pt)` per R-018.5 — top 30% of
    page height in TOP-LEFT-ORIGIN convention."""
    doc = _StubDoc(pages=[_StubPage(width_pt=612.0, height_pt=792.0)])
    s = resolve_region_strategy("header-first-v1")
    bbox = s.page_targeting(doc, 0)
    assert isinstance(bbox, BBox)
    assert bbox.x0_pt == 0.0
    assert bbox.y0_pt == 0.0
    assert bbox.x1_pt == 612.0
    assert bbox.y1_pt == pytest.approx(792.0 * 0.30)


def test_header_first_v1_page_targeting_pages_2_to_n_returns_none() -> None:
    """`header-first-v1.page_targeting(doc, i)` returns `None` for
    every `i > 0` per R-018.5 — the orchestrator interprets `None` from
    `header-first-v1` specifically as 'skip and emit empty page record'."""
    doc = _StubDoc(pages=[
        _StubPage(width_pt=612.0, height_pt=792.0),
        _StubPage(width_pt=612.0, height_pt=792.0),
        _StubPage(width_pt=612.0, height_pt=792.0),
    ])
    s = resolve_region_strategy("header-first-v1")
    assert s.page_targeting(doc, 1) is None
    assert s.page_targeting(doc, 2) is None


def test_header_first_v1_page_targeting_is_deterministic() -> None:
    """FR-006 / I-018.4: two calls of `page_targeting(doc, 0)` on the
    same input return the same `BBox`."""
    doc = _StubDoc(pages=[_StubPage(width_pt=612.0, height_pt=792.0)])
    s = resolve_region_strategy("header-first-v1")
    b1 = s.page_targeting(doc, 0)
    b2 = s.page_targeting(doc, 0)
    assert b1 == b2


@pytest.mark.parametrize(
    "width_pt, height_pt",
    [
        (612.0, 792.0),    # US Letter portrait
        (612.0, 1008.0),   # US Legal portrait
        (842.0, 595.0),    # A4 landscape
        (1224.0, 1584.0),  # 17×22 ledger
    ],
)
def test_header_first_v1_page_targeting_handles_various_page_sizes(
    width_pt: float, height_pt: float,
) -> None:
    """The header band is a constant proportion (30%) of page height
    regardless of orientation or page size (R-018.5)."""
    doc = _StubDoc(pages=[_StubPage(width_pt=width_pt, height_pt=height_pt)])
    s = resolve_region_strategy("header-first-v1")
    bbox = s.page_targeting(doc, 0)
    assert bbox is not None
    assert bbox.x1_pt == width_pt
    assert bbox.y1_pt == pytest.approx(height_pt * 0.30)


# ---------------------------------------------------------------------------
# T022 (e) / I-018.4: full-page strategy returns None on every page
# ---------------------------------------------------------------------------


def test_full_page_targeting_returns_none_on_every_page() -> None:
    """`full-page.page_targeting(doc, i)` returns `None` for every `i`
    (the orchestrator treats `None` as 'process whole page')."""
    doc = _StubDoc(pages=[
        _StubPage(width_pt=612.0, height_pt=792.0) for _ in range(5)
    ])
    s = resolve_region_strategy("full-page")
    for i in range(5):
        assert s.page_targeting(doc, i) is None


def test_full_page_strategy_trigger_never_fires() -> None:
    """Full-page / cpu-default / stub-default strategies have no
    fallback path, so the trigger predicate returns `False` always."""
    for name in ["full-page", "cpu-default", "stub-default"]:
        s = resolve_region_strategy(name)
        assert s.trigger_fired([]) is False


# ---------------------------------------------------------------------------
# T022 (f) / I-018.2: module-load is CPU-safe (no Paddle import)
# ---------------------------------------------------------------------------


def test_region_strategies_module_imports_without_paddle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host without Paddle GPU MUST be able to
    `import ledgerlinc_ocr.preprocessing.region_strategies` cleanly
    (FR-015 / I-018.2)."""
    import importlib

    for mod_name in [
        "ledgerlinc_ocr.preprocessing.region_strategies",
        "paddleocr",
        "paddle",
    ]:
        sys.modules.pop(mod_name, None)
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    monkeypatch.setitem(sys.modules, "paddle", None)
    mod = importlib.import_module(
        "ledgerlinc_ocr.preprocessing.region_strategies"
    )
    assert hasattr(mod, "REGION_STRATEGIES")
    assert "header-first-v1" in mod.REGION_STRATEGIES
