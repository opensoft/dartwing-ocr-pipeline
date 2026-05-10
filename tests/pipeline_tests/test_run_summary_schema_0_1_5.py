"""Run-summary schema 0.1.5 patch-bump tests (feature 018 / T004 / T012 /
T025 / T030 / FR-008 / FR-009 / FR-010 / FR-011 / R-018.14).

Sibling of `test_run_summary_schema_0_1_4.py` (feature 017),
`test_run_summary_schema_0_1_3.py` (feature 016), and
`test_run_summary_schema_0_1_2.py` (feature 015). Adds the
0.1.5-specific regression checks: codebase-level
`SCHEMA_VERSION = "0.1.5"`, three new additive top-level fields
(`raster_profile_id`, `region_strategy_id`,
`region_strategy_fallback_count`) emitted on every run, fixed emission
order AFTER feature 017's three fields and before the closing brace,
default values reflecting CPU-lane defaults from
`preprocessing/identifiers.py`.

T012 (US1) lands the `raster_profile_id` slice; T025 (US2) extends
with `region_strategy_id`; T030 (US3) extends with
`region_strategy_fallback_count` field-level checks. All three slices
live in this same file (cumulative verification).

All tests are CPU-safe (no Paddle import, no GPU dependency).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

timing = pytest.importorskip("ledgerlinc_ocr.pipeline.timing")

from ledgerlinc_ocr.pipeline.timing import (  # noqa: E402
    RunSummary,
    SCHEMA_VERSION,
)
from ledgerlinc_ocr.preprocessing.identifiers import (  # noqa: E402
    CPU_DEFAULT_RASTER_PROFILE,
    CPU_DEFAULT_REGION_STRATEGY,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_minimal_run_summary(**overrides: Any) -> RunSummary:
    """Build a minimal RunSummary with the smallest valid construction
    args; tests override individual fields."""
    base: dict[str, Any] = {
        "stack_preset": None,
        "resolved_profiles": {"preprocess": "ppstructurev3@cpu"},
        "execution_slice": {"start_at": "preprocess", "stop_after": "preprocess"},
        "on_failure": "continue",
        "documents_total": 1,
        "documents_succeeded": 1,
        "documents_failed": 0,
    }
    base.update(overrides)
    return RunSummary(**base)


# ---------------------------------------------------------------------------
# T004 / T012 / R-018.14: codebase-level SCHEMA_VERSION bump 0.1.4 → 0.1.5
# ---------------------------------------------------------------------------


def test_schema_version_is_0_1_5_codebase_level() -> None:
    """`SCHEMA_VERSION` is exactly `"0.1.5"` for every run of the new
    binary regardless of preset selection (per R-018.14 +
    `contracts/run-summary-schema.md` §1)."""
    assert timing.SCHEMA_VERSION == "0.1.5", (
        f"feature 018 must bump SCHEMA_VERSION from 0.1.4 to 0.1.5 "
        f"(got {timing.SCHEMA_VERSION!r})"
    )
    assert SCHEMA_VERSION == "0.1.5"


def test_run_summary_emits_0_1_5_in_json_line() -> None:
    """A serialized `run_summary` line carries `schema_version: "0.1.5"`
    on the wire."""
    summary = _make_minimal_run_summary()
    line = summary.as_json_line()
    parsed = json.loads(line)
    assert parsed["schema_version"] == "0.1.5"


# ---------------------------------------------------------------------------
# T012 / FR-008 / FR-011: raster_profile_id is emitted on every run
# ---------------------------------------------------------------------------


def test_raster_profile_id_present_on_every_run() -> None:
    """Per FR-008 / FR-011 / contracts/run-summary-schema.md §3:
    `raster_profile_id` is required on every run_summary line (absence
    is itself a regression signal)."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "raster_profile_id" in parsed


def test_cpu_lane_default_raster_profile_is_cpu_default() -> None:
    """Default `RunSummary` (no overrides) reflects the CPU lane —
    `raster_profile_id="cpu-default"` per R-018.2 / I-018.9."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert parsed["raster_profile_id"] == CPU_DEFAULT_RASTER_PROFILE == "cpu-default"


def test_raster_profile_id_can_be_overridden() -> None:
    """A GPU run sets `raster_profile_id` to the resolved preset name
    (e.g., `"legacy"` or `"reduced-v1"`) via the dataclass field."""
    for profile_name in ["legacy", "reduced-v1", "stub-default"]:
        summary = _make_minimal_run_summary(raster_profile_id=profile_name)
        parsed = json.loads(summary.as_json_line())
        assert parsed["raster_profile_id"] == profile_name


# ---------------------------------------------------------------------------
# T012 / FR-009 / FR-011: region_strategy_id and region_strategy_fallback_count
# default presence (US2 wiring will write actual GPU values via T025/T030).
# ---------------------------------------------------------------------------


def test_region_strategy_id_present_on_every_run() -> None:
    """Per FR-008 / FR-011 / contracts/run-summary-schema.md §3:
    `region_strategy_id` is required on every run_summary line."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "region_strategy_id" in parsed
    assert parsed["region_strategy_id"] == CPU_DEFAULT_REGION_STRATEGY == "cpu-default"


def test_region_strategy_fallback_count_present_on_every_run() -> None:
    """Per FR-009 / Clarifications Q4: `region_strategy_fallback_count`
    is required on every run_summary line; default `0`."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "region_strategy_fallback_count" in parsed
    assert parsed["region_strategy_fallback_count"] == 0


# ---------------------------------------------------------------------------
# T012 / contracts/run-summary-schema.md §2: emission order is fixed
# ---------------------------------------------------------------------------


def test_three_feature_018_fields_emit_after_feature_017_fields_in_order() -> None:
    """Feature 018's three additive top-level fields land in fixed order
    AFTER feature 017's three fields and before the run_summary's
    terminating brace (contracts/run-summary-schema.md §2). The full
    order at the trailing edge is:

      preprocess_lane (014)
      module_set_id, det_rec_variant_id, ppstructure_modules_invoked (017)
      raster_profile_id, region_strategy_id, region_strategy_fallback_count (018)
    """
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    keys = list(parsed.keys())
    # Anchor at preprocess_lane (014's last additive)
    pl_idx = keys.index("preprocess_lane")
    expected_tail = [
        "preprocess_lane",
        "module_set_id",
        "det_rec_variant_id",
        "ppstructure_modules_invoked",
        "raster_profile_id",
        "region_strategy_id",
        "region_strategy_fallback_count",
    ]
    assert keys[pl_idx:pl_idx + len(expected_tail)] == expected_tail
    # Feature 018's three are the LAST three keys (no later additive)
    assert keys[-3:] == [
        "raster_profile_id",
        "region_strategy_id",
        "region_strategy_fallback_count",
    ]


# ---------------------------------------------------------------------------
# Cross-preset stability: schema_version unchanged across raster_profile
# selections (US1 cumulative coverage)
# ---------------------------------------------------------------------------


def test_schema_version_unchanged_across_raster_profile_selections() -> None:
    """`schema_version` is `"0.1.5"` for every emission regardless of
    which raster_profile the run used — fixed at the codebase level
    (R-018.14)."""
    for raster_profile_id in ["cpu-default", "stub-default", "legacy", "reduced-v1"]:
        summary = _make_minimal_run_summary(raster_profile_id=raster_profile_id)
        parsed = json.loads(summary.as_json_line())
        assert parsed["schema_version"] == "0.1.5", (
            f"schema_version must stay 0.1.5 across all raster_profile "
            f"selections; got {parsed['schema_version']!r} for "
            f"raster_profile_id={raster_profile_id!r}"
        )
