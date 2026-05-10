"""Feature 018: closed-vocabulary region-strategy preset registry.

Houses one named-preset axis:

- `RegionStrategy` (`REGION_STRATEGIES`): selects which region of which
  PDF page is processed by the preprocessing orchestrator. Closed
  vocabulary at landing: `full-page`, `header-first-v1`, `cpu-default`,
  `stub-default`.

Sibling of `preprocessing/raster_profiles.py` (feature 018) and
`preprocessing/presets.py` (feature 017). Shares the same
`UnknownPresetError` (additively widened to four axes per R-018.12) and
the same `ExitCode.UNKNOWN_PRESET = 16` route via the existing CLI catch
sites.

The `header-first-v1` strategy implements the deterministic FR-007
fallback trigger (Clarifications Q3): after region-first preprocessing
of page 1's targeted band completes, if the whitespace-stripped
concatenation of `blocks[].text` in the targeted region is empty, the
orchestrator MUST fall back to the full-page strategy on that document
(R-018.7). This module provides only the trigger predicate; the
orchestrator (`preprocessing/pipeline.py`) owns the discard-and-rerun
action and the per-document fallback accumulator.

Module is **CPU-safe at module-load** — no `import paddleocr` / `import
paddle` at module level (FR-015 / contracts/module-invariants.md
I-018.2). The `pypdfium2` import inside `page_targeting` is deferred to
call-time so a host without Paddle GPU can `import
ledgerlinc_ocr.preprocessing.region_strategies` cleanly. No Paddle
dependency anywhere in this module.

Public API:

- `BBox` — frozen dataclass (PDF-pt coordinates: `x0_pt`, `y0_pt`,
  `x1_pt`, `y1_pt`)
- `Block` — protocol/duck-type for the `text` attribute
  `RegionStrategy.trigger_fired` reads
- `RegionStrategy` — frozen dataclass; carries `name`, `page_targeting`,
  `trigger_fired`
- `REGION_STRATEGIES` — closed-vocabulary registry for region_strategy names
- `resolve_region_strategy(name: str) -> RegionStrategy` — dict-lookup;
  raises `UnknownPresetError(preset_axis="region_strategy", ...)` on miss
- `translate_bbox(crop_relative_bbox, crop_offset_px) -> tuple[int, ...]`
  — coordinate translation helper (T021 / R-018.15) used by the
  orchestrator after PaddleOCR returns crop-relative bboxes.

Decision sources:

- spec.md §FR-004, FR-006, FR-007, FR-008, FR-009; /speckit.clarify
  Q1, Q2, Q3, Q4
- research.md R-018.4 (vocabulary), R-018.5 (header-first heuristic +
  band proportion), R-018.6 (empty-page-record schema), R-018.7
  (fallback trigger and action), R-018.12 (UnknownPresetError reuse),
  R-018.15 (coordinate translation)
- data-model.md §RegionStrategy, §BBox, §UnknownPresetError,
  §"Empty page record"
- contracts/module-invariants.md I-018.1, I-018.2, I-018.4, I-018.5,
  I-018.6, I-018.7, I-018.10
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional, Protocol

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.identifiers import (
    CPU_DEFAULT_REGION_STRATEGY,
    LEGACY_REGION_STRATEGY,
    STUB_DEFAULT_REGION_STRATEGY,
)


# ---------------------------------------------------------------------------
# BBox dataclass (PDF-pt coordinates)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BBox:
    """A bounding box in PDF point coordinates (R-018.5 / data-model.md §BBox).

    PDF coordinate convention: origin at top-left, y increases downward
    (matches `pypdfium2`'s rendering API for the bitmap output, NOT the
    PostScript/PDF-native bottom-left-origin convention used by
    `pypdfium2.PdfPage.get_size()` for raw point measurements). The
    rasterizer's `rasterize_page_band` is responsible for applying the
    correct axis flip when cropping; this BBox is the orchestrator-side
    representation in the top-left-origin space.

    Conversion to pixel coordinates: `x_px = x_pt * dpi / 72.0`,
    `y_px = y_pt * dpi / 72.0`. The rasterizer applies this conversion
    when cropping; the orchestrator applies the inverse offset when
    translating PaddleOCR's crop-relative pixel bboxes back to
    full-page pixel coordinates (R-018.15).
    """

    x0_pt: float
    y0_pt: float
    x1_pt: float
    y1_pt: float


# ---------------------------------------------------------------------------
# Block protocol (duck-type for trigger_fired)
# ---------------------------------------------------------------------------


class Block(Protocol):
    """Duck-type for the `text` attribute `trigger_fired` reads.

    The actual block class lives in `preprocessing/pipeline.py` (it
    builds the `preprocess_output.json` per-page block records). Using a
    Protocol here avoids a circular import and lets unit tests pass
    simple stubs to `trigger_fired` without instantiating real
    pipeline-side block records.
    """

    text: str


# ---------------------------------------------------------------------------
# RegionStrategy dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionStrategy:
    """Named region-strategy preset (R-018.4 / data-model.md §RegionStrategy).

    `name` is drawn from the closed `REGION_STRATEGIES.keys()` vocabulary;
    `page_targeting` is a deterministic function of `(pdf_doc, page_index)`
    returning the targeted BBox in PDF-pt coordinates or `None`;
    `trigger_fired` is a deterministic predicate over the targeted
    region's blocks that fires when fallback should occur.

    Frozen so registry entries can be safely shared across the process
    lifetime without defensive copies. The Callables themselves are
    pure functions (no captured state).
    """

    name: str
    page_targeting: Callable[[Any, int], Optional[BBox]]
    trigger_fired: Callable[[list[Any]], bool]


# ---------------------------------------------------------------------------
# Strategy implementations (CPU-safe — no Paddle dependency)
# ---------------------------------------------------------------------------


def _full_page_targeting(pdf_doc: Any, page_index: int) -> Optional[BBox]:
    """Identity strategy: process the whole page (no cropping). The
    orchestrator interprets `None` from a `full-page`-class strategy as
    'process whole page'."""
    return None


def _no_fallback(blocks: list[Any]) -> bool:
    """Identity trigger predicate: full-page / cpu-default / stub-default
    strategies have no fallback path, so the trigger never fires."""
    return False


# Header-first-v1 band proportion: top 30% of page height per R-018.5.
# Hard-coded constant; NOT exposed on the runtime path (FR-004 — preset
# names only, no free-form coordinates) and NOT computed from page
# content (FR-006 — page-targeting MUST NOT depend on extraction or
# vendor-identity model output).
_HEADER_FIRST_V1_BAND_PROPORTION: float = 0.30


def _header_first_v1_targeting(pdf_doc: Any, page_index: int) -> Optional[BBox]:
    """Page-targeting rule for `header-first-v1` (R-018.5):

    - For page 1 (`page_index == 0`): return the top 30% of page height
      as a BBox in PDF-pt coordinates (top-left-origin convention).
    - For pages 2..N (`page_index > 0`): return `None`. The orchestrator
      interprets `None` from `header-first-v1` specifically as 'skip
      this page and emit an empty page record' (R-018.6 / Clarifications
      Q2). The `pages.length == page_count` invariant is preserved by
      the orchestrator emitting an empty page record for these pages.

    Deterministic per FR-006: the targeting decision is a pure function
    of `(pdf_doc, page_index)` — no model output, no wall-clock time, no
    random seed.
    """
    if page_index != 0:
        return None
    page = pdf_doc.get_page(page_index)
    try:
        width_pt, height_pt = page.get_size()
    finally:
        page.close()
    band_height_pt = float(height_pt) * _HEADER_FIRST_V1_BAND_PROPORTION
    return BBox(
        x0_pt=0.0,
        y0_pt=0.0,
        x1_pt=float(width_pt),
        y1_pt=band_height_pt,
    )


def _header_first_v1_trigger(blocks: list[Any]) -> bool:
    """FR-007 fallback trigger for `header-first-v1` (Clarifications Q3
    / R-018.7).

    Returns `True` iff the concatenation of `blocks[].text` (across all
    targeted-region blocks for page 1), with whitespace stripped, is
    empty. Pure deterministic check — no model output beyond what
    produced the blocks themselves; re-derivable from
    `preprocess_output.json` alone.

    The orchestrator (`preprocessing/pipeline.py`) is responsible for
    the fallback ACTION: discard the partial output, re-preprocess the
    document under the full-page strategy on the same engine instance
    (R-018.9), accumulate combined wall-clock cost into the per-document
    `phase_timings.rasterization` / `phase_timings.per_page_inference`
    (R-018.10), and increment the run-level
    `region_strategy_fallback_count` by 1.

    Per I-018.5: the trigger inspects ONLY `blocks[].text` — NOT
    `raw_ocr_lines[].text`, NOT bounding-box presence, NOT block count.
    """
    return not "".join(getattr(b, "text", "") for b in blocks).strip()


# ---------------------------------------------------------------------------
# Closed-vocabulary registry (R-018.4)
# ---------------------------------------------------------------------------
#
# Four registry entries at landing: `full-page` (legacy GPU default),
# `header-first-v1` (the new region-first preset), and two identity
# aliases for the CPU lane and stub adapter (which never run the
# region-first targeting because FR-014 warn-and-proceed nulls the
# threaded value before it reaches the orchestrator).
#
# The CPU/stub identity aliases share the `_full_page_targeting` /
# `_no_fallback` callables with `full-page` — they exist purely to
# populate the run_summary identifier surface on every run (FR-011);
# the actual page processing is identical to a no-flag CPU run.
REGION_STRATEGIES: Mapping[str, RegionStrategy] = MappingProxyType({
    LEGACY_REGION_STRATEGY: RegionStrategy(
        name=LEGACY_REGION_STRATEGY,
        page_targeting=_full_page_targeting,
        trigger_fired=_no_fallback,
    ),
    "header-first-v1": RegionStrategy(
        name="header-first-v1",
        page_targeting=_header_first_v1_targeting,
        trigger_fired=_header_first_v1_trigger,
    ),
    CPU_DEFAULT_REGION_STRATEGY: RegionStrategy(
        name=CPU_DEFAULT_REGION_STRATEGY,
        page_targeting=_full_page_targeting,
        trigger_fired=_no_fallback,
    ),
    STUB_DEFAULT_REGION_STRATEGY: RegionStrategy(
        name=STUB_DEFAULT_REGION_STRATEGY,
        page_targeting=_full_page_targeting,
        trigger_fired=_no_fallback,
    ),
})


# ---------------------------------------------------------------------------
# Resolver (R-018.12 — raises UnknownPresetError on miss)
# ---------------------------------------------------------------------------


def resolve_region_strategy(name: str) -> RegionStrategy:
    """Look up a `RegionStrategy` by name in the closed registry.

    Raises `UnknownPresetError(preset_axis="region_strategy", ...)` if
    `name` is not a registered key — surfaced to the operator as
    `error: unknown region_strategy: <name!r> — valid values are: <…>`
    on stderr with exit code 16 (`ExitCode.UNKNOWN_PRESET`) per the
    existing CLI catch sites in `preprocessing/cli.py` and
    `pipeline/cli.py` (no caller change needed; the additively widened
    `preset_axis: Literal[…]` from R-018.12 is what enables the new
    axis to flow through the existing route).
    """
    try:
        return REGION_STRATEGIES[name]
    except KeyError:
        raise UnknownPresetError(
            f"unknown region_strategy: {name!r}",
            preset_axis="region_strategy",
            preset_value=name,
            valid_values=tuple(REGION_STRATEGIES.keys()),
        )


# ---------------------------------------------------------------------------
# T021 / R-018.15: coordinate translation helper
# ---------------------------------------------------------------------------


def translate_bbox(
    crop_relative_bbox: tuple[int, int, int, int],
    crop_offset_px: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Translate a PaddleOCR-returned crop-relative pixel bbox back to
    full-page pixel coordinates by adding the crop's top-left offset.

    For `header-first-v1` (R-018.5), the crop is at page top-left so
    the offset is `(0, 0)` and this is the identity. The helper exists
    as a guard rail for any future preset that crops a non-top-left
    region — the orchestrator should ALWAYS run PaddleOCR's bbox returns
    through this helper before placing them in
    `preprocess_output.json.pages[].blocks[].bbox` /
    `pages[].raw_ocr_lines[].bbox` so coordinates stay in the
    full-page-origin convention required by FR-002 / I-018.7.

    `bbox` is `(x0, y0, x1, y1)` in pixel space; `crop_offset_px` is
    `(dx, dy)` in pixel space.
    """
    dx, dy = crop_offset_px
    x0, y0, x1, y1 = crop_relative_bbox
    return (x0 + dx, y0 + dy, x1 + dx, y1 + dy)


__all__ = (
    "BBox",
    "Block",
    "RegionStrategy",
    "REGION_STRATEGIES",
    "resolve_region_strategy",
    "translate_bbox",
)
