"""Feature 018: closed-vocabulary rasterization-DPI preset registry.

Houses one named-preset axis:

- `RasterProfile` (`RASTER_PROFILES`): selects the rasterization DPI used
  by `rasterize_pdf(...)` and `rasterize_page_band(...)`. Closed
  vocabulary at landing: `legacy`, `reduced-v1`, `cpu-default`,
  `stub-default`.

Sibling of `preprocessing/presets.py` (feature 017) and
`preprocessing/region_strategies.py` (feature 018); shares the same
`UnknownPresetError` (additively widened to four axes per R-018.12) and
the same `ExitCode.UNKNOWN_PRESET = 16` route via the existing CLI catch
sites.

Module is **CPU-safe at module-load** — no `import paddleocr` / `import
paddle` at module level (FR-015 / contracts/module-invariants.md
I-018.2). Only `from ledgerlinc_ocr.preprocessing.version import DPI` is
imported at module load, so a host without Paddle GPU can
`import ledgerlinc_ocr.preprocessing.raster_profiles` cleanly.

Public API:

- `RasterProfile` — frozen dataclass; carries `name`, `dpi`
- `RASTER_PROFILES` — closed-vocabulary registry for raster_profile names
- `resolve_raster_profile(name: str) -> RasterProfile` — dict-lookup;
  raises `UnknownPresetError(preset_axis="raster_profile", ...)` on miss

Decision sources:

- spec.md §FR-001, FR-002, FR-003, FR-008, FR-014, FR-015; /speckit.clarify
- research.md R-018.1 (activation), R-018.2 (vocabulary),
  R-018.3 (`reduced-v1` DPI value), R-018.12 (UnknownPresetError reuse),
  R-018.14 (SCHEMA_VERSION 0.1.5 bump)
- data-model.md §RasterProfile, §UnknownPresetError, §Identifier-string constants
- contracts/module-invariants.md I-018.1, I-018.2, I-018.11
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError
from ledgerlinc_ocr.preprocessing.identifiers import (
    CPU_DEFAULT_RASTER_PROFILE,
    LEGACY_RASTER_PROFILE,
    STUB_DEFAULT_RASTER_PROFILE,
)
from ledgerlinc_ocr.preprocessing.version import DPI


# ---------------------------------------------------------------------------
# RasterProfile dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RasterProfile:
    """Named rasterization-DPI preset (R-018.2 / data-model.md §RasterProfile).

    `name` is drawn from the closed `RASTER_PROFILES.keys()` vocabulary;
    `dpi` is the integer DPI passed to the rasterizer's per-page render
    call. Frozen so registry entries can be safely shared across the
    process lifetime without defensive copies.
    """

    name: str
    dpi: int


# ---------------------------------------------------------------------------
# Closed-vocabulary registry (R-018.2)
# ---------------------------------------------------------------------------
#
# Single-source-of-truth for `legacy.dpi`: the value is read from
# `preprocessing/version.py:DPI` at module-load time per I-018.11. If
# `version.DPI` ever changes in a future feature, `legacy` follows it
# without any code change here. There MUST NOT be a duplicate hard-coded
# `300` in this file.
#
# `reduced-v1.dpi = 200` per R-018.3 — chosen as a safety-comfortable
# reduction from 300 DPI that still keeps a margin above the ~150 DPI
# floor where PaddleOCR detection recall on small text starts to degrade.
#
# `cpu-default` and `stub-default` are identity presets for the CPU lane
# and stub adapter respectively — `dpi = 300` matches the CPU rasterizer's
# existing module-level `DPI` constant and the stub adapter (which never
# actually rasterizes). Their existence populates the
# `run_summary.raster_profile_id` identifier surface on every run
# (FR-011); the CPU rasterizer is NOT preset-driven (FR-015 / I-018.2).
RASTER_PROFILES: Mapping[str, RasterProfile] = MappingProxyType({
    LEGACY_RASTER_PROFILE: RasterProfile(name=LEGACY_RASTER_PROFILE, dpi=DPI),
    "reduced-v1": RasterProfile(name="reduced-v1", dpi=200),
    CPU_DEFAULT_RASTER_PROFILE: RasterProfile(name=CPU_DEFAULT_RASTER_PROFILE, dpi=DPI),
    STUB_DEFAULT_RASTER_PROFILE: RasterProfile(name=STUB_DEFAULT_RASTER_PROFILE, dpi=DPI),
})


# ---------------------------------------------------------------------------
# Resolver (R-018.12 — raises UnknownPresetError on miss)
# ---------------------------------------------------------------------------


def resolve_raster_profile(name: str) -> RasterProfile:
    """Look up a `RasterProfile` by name in the closed registry.

    Raises `UnknownPresetError(preset_axis="raster_profile", ...)` if
    `name` is not a registered key — surfaced to the operator as
    `error: unknown raster_profile: <name!r> — valid values are: <…>`
    on stderr with exit code 16 (`ExitCode.UNKNOWN_PRESET`) per the
    existing CLI catch sites in `preprocessing/cli.py` and
    `pipeline/cli.py` (no caller change needed; the additively widened
    `preset_axis: Literal[…]` from R-018.12 is what enables the new
    axis to flow through the existing route).
    """
    try:
        return RASTER_PROFILES[name]
    except KeyError:
        raise UnknownPresetError(
            f"unknown raster_profile: {name!r}",
            preset_axis="raster_profile",
            preset_value=name,
            valid_values=tuple(RASTER_PROFILES.keys()),
        )
