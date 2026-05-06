"""Pipeline version string assembly (FR-004, FR-008, research R-007).

Feature 014 extends this module to add a trailing lane segment
(`.cpu` or `.gpu<N>`) to `pipeline_version` per Research R-014.2 and
adds `parse_lane_segment` per data-model.md §LaneSegment.
"""

from __future__ import annotations

import hashlib
import re
from importlib import metadata
from pathlib import Path
from typing import Optional

DPI = 300
CONTRACT_SET_VERSION = "1.2.0"
SEMVER = "v0.2.0"
SLICE_PREFIX = "stage1-preprocess"

# Normative regex for the post-feature pipeline_version (Research R-014.2).
# Captures paddleocr_version, weights_hash7, dpi, and lane_segment.
_PIPELINE_VERSION_RE = re.compile(
    r"^stage1-preprocess-v\d+\.\d+\.\d+\+paddleocr"
    r"(?P<paddleocr_version>\d+\.\d+\.\d+)\."
    r"(?P<weights_hash7>[0-9a-f]{7})\."
    r"dpi(?P<dpi>\d+)\."
    r"(?P<lane_segment>cpu|gpu\d+)$"
)
# Pre-feature regex (no trailing lane segment) — matches the literal CPU
# output emitted before feature 014 landed. Used by parse_lane_segment's
# backward-compat default (data-model §LaneSegment).
_PRE_FEATURE_RE = re.compile(
    r"^stage1-preprocess-v\d+\.\d+\.\d+\+paddleocr"
    r"\d+\.\d+\.\d+\.[0-9a-f]{7}\.dpi\d+$"
)
# Permissive regex (forward-compat tolerance) — matches the post-feature
# shape with any single trailing dot-segment, including unrecognized
# lane segments like `.npu0` or `.jetson1`. Compiled at module scope so
# it is built once at import time rather than once per parse_lane_segment
# call. Used only by parse_lane_segment's forward-compat fallback branch.
_PERMISSIVE_PIPELINE_VERSION_RE = re.compile(
    r"^stage1-preprocess-v\d+\.\d+\.\d+\+paddleocr"
    r"\d+\.\d+\.\d+\.[0-9a-f]{7}\.dpi\d+\.[A-Za-z0-9_]+$"
)


def build_pipeline_version(
    semver: str = SEMVER,
    paddleocr_version: str | None = None,
    weights_hash7: str | None = None,
    dpi: int = DPI,
    lane_segment: str = "cpu",
) -> str:
    """Build the canonical pipeline_version string.

    Feature 014 (R-014.2) appends a trailing `.{lane_segment}` segment
    after `dpi{dpi}`. The CPU default is `lane_segment="cpu"`; the GPU
    lane uses `lane_segment="gpu0"` (or `gpu<N>` for non-zero device
    indices, reserved for future multi-GPU work). Existing callers
    that omit `lane_segment` continue to emit a valid post-feature
    string ending `.cpu` — matching the FR-016 mandate that every
    post-feature artifact carry a lane segment.
    """
    if paddleocr_version is None:
        paddleocr_version = metadata.version("paddleocr")
    if weights_hash7 is None:
        weights_hash7 = "0000000"
    return (
        f"{SLICE_PREFIX}-{semver}+paddleocr{paddleocr_version}."
        f"{weights_hash7}.dpi{dpi}.{lane_segment}"
    )


def parse_lane_segment(pipeline_version: str) -> tuple[str, Optional[int]]:
    """Parse the trailing lane segment of a pipeline_version string.

    Behavior per data-model.md §LaneSegment:

    - For a post-feature CPU string ending in `.cpu`: returns `("cpu", None)`.
    - For a post-feature GPU string ending in `.gpu<N>`: returns `("gpu", N)`.
    - For a pre-feature `pipeline_version` (no trailing lane segment, ends
      with `.dpi<N>`): returns `("cpu", None)` per the backward-compat
      default — pre-feature artifacts were always CPU-produced.
    - For a forward-compatible unknown segment (e.g. `.npu0`, `.jetson0`,
      anything not matching `cpu|gpu\\d+`): returns `("unknown", None)`
      and does NOT raise. Strict consumers in future features may upgrade
      to a fail-fast policy; today's parser tolerates unrecognized
      segments.
    - For a malformed `pipeline_version` (empty, missing `dpi<N>`, missing
      the `+paddleocr…` block): raises a `ValueError`.
    """
    if not isinstance(pipeline_version, str) or not pipeline_version:
        raise ValueError(f"malformed pipeline_version: {pipeline_version!r}")
    m = _PIPELINE_VERSION_RE.match(pipeline_version)
    if m is not None:
        seg = m.group("lane_segment")
        if seg == "cpu":
            return ("cpu", None)
        # seg matches "gpu<N>" by regex; extract the integer
        return ("gpu", int(seg[3:]))
    # Pre-feature backward-compat default: missing trailing lane segment.
    if _PRE_FEATURE_RE.match(pipeline_version):
        return ("cpu", None)
    # Forward-compat tolerance: looks like a pipeline_version but the
    # trailing segment is unrecognized (e.g. `.npu0`, `.jetson1`).
    # Permit the prefix to match the pre-feature shape with any extra
    # trailing dot-segment (single segment, no embedded dots). The regex
    # is precompiled at module scope (`_PERMISSIVE_PIPELINE_VERSION_RE`)
    # so this branch does not re-compile on every call.
    if _PERMISSIVE_PIPELINE_VERSION_RE.match(pipeline_version):
        return ("unknown", None)
    raise ValueError(f"malformed pipeline_version: {pipeline_version!r}")


def hash_weights(weight_paths: list[Path]) -> str:
    """Return the first 7 hex chars of a stable hash over the given weight files."""
    digest = hashlib.sha256()
    for p in sorted(weight_paths, key=lambda x: str(x)):
        digest.update(str(p).encode("utf-8"))
        digest.update(b"\0")
        with p.open("rb") as f:
            while chunk := f.read(1 << 20):
                digest.update(chunk)
    return digest.hexdigest()[:7]
