"""Profile vocabulary tests for feature 014 (T017).

Asserts:
- (a) `parse_profile("preprocess", "ppstructurev3@gpu")` returns a valid `StageProfile` with `lane="gpu"` (FR-007).
- (b) `parse_profile("preprocess", "stub@gpu")` raises `ProfileValidationError` (FR-011, edge case bullet 5).
- (c) `parse_profile("preprocess", "ppstructurev3@cpu")` continues to behave as before.
- (d) When `--preprocess-profile` is omitted from CLI invocation, the resolved default is `ppstructurev3@cpu` (VT4 / FR-008).
- (e) The default `pipeline_version` parses via `parse_lane_segment(...)` to `("cpu", None)` (FR-016 CPU-side).
"""
from __future__ import annotations

import pytest

from ledgerlinc_ocr.pipeline.profiles import (
    DEFAULT_PROFILES,
    PPSTRUCTUREV3_CPU,
    PPSTRUCTUREV3_GPU,
    ProfileValidationError,
    parse_profile,
    resolve_profiles,
)


def test_parse_ppstructurev3_gpu_accepted() -> None:
    p = parse_profile("preprocess", "ppstructurev3@gpu")
    assert p.kind == "live"
    assert p.implementation == "ppstructurev3"
    assert p.lane == "gpu"
    assert p.raw_value == "ppstructurev3@gpu"


def test_parse_ppstructurev3_cpu_unchanged() -> None:
    p = parse_profile("preprocess", "ppstructurev3@cpu")
    assert p.lane == "cpu"
    assert p.implementation == "ppstructurev3"


def test_parse_stub_gpu_rejected() -> None:
    """FR-011 + edge case bullet 5: stub remains lane-less; stub@gpu invalid."""
    with pytest.raises(ProfileValidationError):
        parse_profile("preprocess", "stub@gpu")


def test_default_profiles_preprocess_remains_cpu() -> None:
    """FR-008: CPU profile remains the default when no override is passed."""
    assert DEFAULT_PROFILES["preprocess"] == PPSTRUCTUREV3_CPU


def test_resolve_profiles_no_override_yields_cpu() -> None:
    """VT4 (analyze finding): when --preprocess-profile is omitted, the
    resolved profile is ppstructurev3@cpu and its lane is 'cpu'."""
    profiles, preset_name = resolve_profiles(
        stack_preset=None,
        explicit={"preprocess": None, "extract": None, "routing": None, "final_payload": None},
    )
    assert profiles["preprocess"].raw_value == PPSTRUCTUREV3_CPU
    assert profiles["preprocess"].lane == "cpu"


def test_default_pipeline_version_parses_to_cpu_lane() -> None:
    """FR-016 CPU-side: default build_pipeline_version() emits .cpu and
    parse_lane_segment recovers ('cpu', None)."""
    from ledgerlinc_ocr.preprocessing.version import (
        build_pipeline_version,
        parse_lane_segment,
    )

    s = build_pipeline_version()
    assert s.endswith(".cpu")
    assert parse_lane_segment(s) == ("cpu", None)


def test_supported_profiles_contains_gpu_tuple() -> None:
    from ledgerlinc_ocr.pipeline.profiles import SUPPORTED_PROFILES

    assert ("preprocess", "ppstructurev3", "gpu") in SUPPORTED_PROFILES
    assert ("preprocess", "ppstructurev3", "cpu") in SUPPORTED_PROFILES


def test_ppstructurev3_gpu_constant_defined() -> None:
    assert PPSTRUCTUREV3_GPU == "ppstructurev3@gpu"
