"""Unit tests for the closed-set profile resolver.

Covers Spec FR-005 / FR-006 / FR-008 / FR-004A; Research R-001 / R-002 /
R-003. Design checklist CHK009-CHK012.
"""
from __future__ import annotations

import pytest

from dartwing_ocr.pipeline.profiles import (
    DEFAULT_PROFILES,
    STACK_PRESETS,
    SUPPORTED_PROFILES,
    ProfileValidationError,
    expand_stack_preset,
    parse_profile,
    resolve_profiles,
)


# ---------------------------------------------------------------------------
# Accepted values per FR-006
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stage,raw",
    [
        ("preprocess", "stub"),
        ("preprocess", "ppstructurev3@cpu"),
        ("preprocess", "edge-ocr@jetson"),
        ("extract", "stub"),
        ("extract", "ollama@gpu"),
        ("extract", "ollama@cpu"),
        ("extract", "ollama@jetson"),
        ("extract", "ensemble@workstation"),
        ("routing", "stub"),
        ("routing", "rules@cpu"),
        ("final_payload", "stub"),
        ("final_payload", "assembler@cpu"),
    ],
)
def test_parse_profile_accepts_every_supported_value(stage, raw):
    profile = parse_profile(stage, raw)
    assert profile.raw_value == raw
    if raw == "stub":
        assert profile.kind == "stub"
        assert profile.lane is None
    else:
        assert profile.kind == "live"
        impl, lane = raw.split("@", 1)
        assert profile.implementation == impl
        assert profile.lane == lane


def test_supported_profiles_matches_fr_006_count():
    # Sanity check: 12 (stage, impl, lane) triples per FR-006.
    assert len(SUPPORTED_PROFILES) == 12


# ---------------------------------------------------------------------------
# Rejection cases (R-002 + spec Edge Cases)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "stage,raw",
    [
        ("preprocess", "stub@cpu"),
        ("preprocess", "stub@gpu"),
        ("extract", "stub@cpu"),
        ("routing", "stub@gpu"),
        ("final_payload", "stub@workstation"),
    ],
)
def test_parse_profile_rejects_stub_with_lane(stage, raw):
    with pytest.raises(ProfileValidationError, match="stub is lane-less"):
        parse_profile(stage, raw)


@pytest.mark.parametrize(
    "stage,raw",
    [
        ("preprocess", "ppstructurev3@gpu"),
        ("preprocess", "edge-ocr@cpu"),
        ("preprocess", "edge-ocr@gpu"),
        ("extract", "ensemble@cloud"),
        ("extract", "ollama@workstation"),
        ("extract", "gemma"),  # missing @lane
        ("extract", "gemma@cpu"),  # unknown implementation
        ("routing", "rules@gpu"),
        ("routing", "rules@jetson"),
        ("final_payload", "assembler@gpu"),
    ],
)
def test_parse_profile_rejects_unsupported_combinations(stage, raw):
    with pytest.raises(ProfileValidationError):
        parse_profile(stage, raw)


@pytest.mark.parametrize("raw", ["", "@", "@cpu", "ollama@", "a@b@c"])
def test_parse_profile_rejects_malformed_grammar(raw):
    with pytest.raises(ProfileValidationError):
        parse_profile("extract", raw)


def test_parse_profile_error_lists_accepted_values_for_stage():
    with pytest.raises(ProfileValidationError) as excinfo:
        parse_profile("routing", "rules@gpu")
    msg = str(excinfo.value)
    assert "rules@cpu" in msg  # advertise the accepted alternative
    assert "stub" in msg


# ---------------------------------------------------------------------------
# Stack preset expansion (R-003)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["full-workstation", "cloud-workstation", "edge-fast"])
def test_expand_stack_preset_known_names(name):
    out = expand_stack_preset(name)
    assert set(out.keys()) == {"preprocess", "extract", "routing", "final_payload"}
    assert all(isinstance(v, str) for v in out.values())


def test_expand_stack_preset_full_workstation_table():
    assert expand_stack_preset("full-workstation") == {
        "preprocess": "ppstructurev3@cpu",
        "extract": "ollama@gpu",
        "routing": "rules@cpu",
        "final_payload": "assembler@cpu",
    }


def test_expand_stack_preset_cloud_workstation_table():
    assert expand_stack_preset("cloud-workstation") == {
        "preprocess": "ppstructurev3@cpu",
        "extract": "ensemble@workstation",
        "routing": "rules@cpu",
        "final_payload": "assembler@cpu",
    }


def test_expand_stack_preset_edge_fast_table():
    assert expand_stack_preset("edge-fast") == {
        "preprocess": "edge-ocr@jetson",
        "extract": "ollama@jetson",
        "routing": "rules@cpu",
        "final_payload": "assembler@cpu",
    }


def test_expand_stack_preset_rejects_unknown():
    with pytest.raises(ProfileValidationError):
        expand_stack_preset("unknown-stack")


# ---------------------------------------------------------------------------
# resolve_profiles (overrides + preset interaction, defaults)
# ---------------------------------------------------------------------------

def test_resolve_profiles_no_preset_uses_default_table():
    profiles, preset_name = resolve_profiles(
        stack_preset=None,
        explicit={"preprocess": None, "extract": None, "routing": None, "final_payload": None},
    )
    assert preset_name is None
    assert {s: p.raw_value for s, p in profiles.items()} == DEFAULT_PROFILES


def test_resolve_profiles_preset_records_name():
    profiles, preset_name = resolve_profiles(
        stack_preset="cloud-workstation",
        explicit={"preprocess": None, "extract": None, "routing": None, "final_payload": None},
    )
    assert preset_name == "cloud-workstation"
    assert profiles["extract"].raw_value == "ensemble@workstation"


def test_resolve_profiles_per_stage_override_wins_over_preset():
    profiles, preset_name = resolve_profiles(
        stack_preset="cloud-workstation",
        explicit={
            "preprocess": None,
            "extract": "ollama@gpu",  # override the preset's ensemble@workstation
            "routing": None,
            "final_payload": None,
        },
    )
    assert preset_name == "cloud-workstation"  # preset name is still recorded
    assert profiles["extract"].raw_value == "ollama@gpu"
    assert profiles["preprocess"].raw_value == "ppstructurev3@cpu"


def test_resolve_profiles_explicit_only_no_preset():
    profiles, preset_name = resolve_profiles(
        stack_preset=None,
        explicit={
            "preprocess": "stub",
            "extract": "stub",
            "routing": "stub",
            "final_payload": "stub",
        },
    )
    assert preset_name is None
    assert all(p.raw_value == "stub" for p in profiles.values())


def test_resolve_profiles_unknown_preset_rejected():
    with pytest.raises(ProfileValidationError):
        resolve_profiles(
            stack_preset="bogus",
            explicit={"preprocess": None, "extract": None, "routing": None, "final_payload": None},
        )


def test_resolve_profiles_invalid_explicit_rejected_under_preset():
    with pytest.raises(ProfileValidationError):
        resolve_profiles(
            stack_preset="full-workstation",
            explicit={
                "preprocess": None,
                "extract": "rules@gpu",  # invalid per FR-008
                "routing": None,
                "final_payload": None,
            },
        )


def test_stack_presets_table_immutable_to_caller():
    """expand_stack_preset returns a defensive copy so a caller can't mutate the global table."""
    out = expand_stack_preset("full-workstation")
    out["preprocess"] = "stub"
    fresh = expand_stack_preset("full-workstation")
    assert fresh["preprocess"] == "ppstructurev3@cpu"
