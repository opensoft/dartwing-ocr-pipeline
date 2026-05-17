"""US5 / T053: stack-preset expansion + override semantics.

Spec FR-004A; Research R-003. Design checklist CHK011 / CHK012.

This is the unit-level expansion table test that complements
test_profile_resolver's preset coverage.
"""
from __future__ import annotations

import pytest

from dartwing_ocr.pipeline.profiles import (
    STACK_PRESETS,
    expand_stack_preset,
    resolve_profiles,
)


def test_all_three_preset_names_in_stack_presets_table():
    assert set(STACK_PRESETS.keys()) == {
        "full-workstation",
        "cloud-workstation",
        "edge-fast",
    }


def test_full_workstation_table_pinned():
    assert expand_stack_preset("full-workstation") == {
        "preprocess": "ppstructurev3@cpu",
        "extract": "ollama@gpu",
        "routing": "rules@cpu",
        "final_payload": "assembler@cpu",
    }


def test_cloud_workstation_table_pinned():
    assert expand_stack_preset("cloud-workstation") == {
        "preprocess": "ppstructurev3@cpu",
        "extract": "ensemble@workstation",
        "routing": "rules@cpu",
        "final_payload": "assembler@cpu",
    }


def test_edge_fast_table_pinned():
    assert expand_stack_preset("edge-fast") == {
        "preprocess": "edge-ocr@jetson",
        "extract": "ollama@jetson",
        "routing": "rules@cpu",
        "final_payload": "assembler@cpu",
    }


def test_per_stage_override_wins_over_preset():
    profiles, preset = resolve_profiles(
        stack_preset="cloud-workstation",
        explicit={
            "preprocess": None,
            "extract": "ollama@gpu",  # override
            "routing": None,
            "final_payload": None,
        },
    )
    assert preset == "cloud-workstation"  # name still recorded
    assert profiles["extract"].raw_value == "ollama@gpu"


def test_preset_name_recorded_even_with_full_override():
    """If every stage is overridden, the preset name is still recorded for metadata."""
    profiles, preset = resolve_profiles(
        stack_preset="full-workstation",
        explicit={
            "preprocess": "stub",
            "extract": "stub",
            "routing": "stub",
            "final_payload": "stub",
        },
    )
    assert preset == "full-workstation"
    assert all(p.raw_value == "stub" for p in profiles.values())
