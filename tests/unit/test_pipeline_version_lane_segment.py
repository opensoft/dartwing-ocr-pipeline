"""Lane-segment grammar round-trip tests (T012 / SC-005 / R-014.2).

Unit-level: exercises `build_pipeline_version(lane_segment=...)` and
`parse_lane_segment(pipeline_version)` in isolation against synthetic
strings. End-to-end byte-stability on a real PDF is tested separately
in T031 (Phase 6 polish). The 3-phase gap is intentional per
analyze finding NEW.13.
"""
from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.version import (
    build_pipeline_version,
    parse_lane_segment,
)


def test_round_trip_cpu_lane() -> None:
    s = build_pipeline_version(lane_segment="cpu")
    assert s.endswith(".cpu")
    assert parse_lane_segment(s) == ("cpu", None)


@pytest.mark.parametrize("device_idx", [0, 1, 7])
def test_round_trip_gpu_lane(device_idx: int) -> None:
    s = build_pipeline_version(lane_segment=f"gpu{device_idx}")
    assert s.endswith(f".gpu{device_idx}")
    assert parse_lane_segment(s) == ("gpu", device_idx)


def test_pre_feature_string_parses_as_cpu() -> None:
    """Backward-compat default per data-model §LaneSegment: a literal
    pre-feature CPU output string (ending exactly at `dpi300`, no lane
    segment) must parse as `("cpu", None)`. This is the contract
    pre-feature artifact consumers depend on (analyze finding M5)."""
    pre_feature = "stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300"
    assert parse_lane_segment(pre_feature) == ("cpu", None)


def test_unknown_segment_returns_unknown_does_not_raise() -> None:
    """Forward-compat tolerance: unrecognized lane segments parse as
    ('unknown', None) without raising."""
    npu = "stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.npu0"
    assert parse_lane_segment(npu) == ("unknown", None)
    jetson = "stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.jetson1"
    assert parse_lane_segment(jetson) == ("unknown", None)


def test_malformed_strings_raise_value_error() -> None:
    """Genuinely malformed strings (missing dpi, missing paddleocr block,
    empty) raise ValueError."""
    with pytest.raises(ValueError):
        parse_lane_segment("garbage")
    with pytest.raises(ValueError):
        parse_lane_segment("")
    with pytest.raises(ValueError):
        parse_lane_segment("stage1-preprocess-v0.2.0")


def test_post_feature_outputs_match_normative_regex() -> None:
    """Per Research R-014.2: every post-feature output of build_pipeline_version
    must match the documented regex."""
    from ledgerlinc_ocr.preprocessing.version import _PIPELINE_VERSION_RE

    cpu = build_pipeline_version()
    assert _PIPELINE_VERSION_RE.match(cpu) is not None

    gpu0 = build_pipeline_version(lane_segment="gpu0")
    assert _PIPELINE_VERSION_RE.match(gpu0) is not None
    m = _PIPELINE_VERSION_RE.match(gpu0)
    assert m.group("lane_segment") == "gpu0"
    assert m.group("dpi") == "300"


def test_default_lane_segment_is_cpu() -> None:
    """build_pipeline_version() with no lane_segment argument emits .cpu
    so post-feature CPU runs uniformly carry the lane segment per
    FR-016."""
    s = build_pipeline_version()
    assert s.endswith(".cpu")
    assert parse_lane_segment(s) == ("cpu", None)
