"""Run-summary schema 0.1.6 patch-bump tests (feature 019 / T004 / T015 /
T019 / T024 / FR-007 / FR-008 / FR-010 / R-019.14).

Sibling of `test_run_summary_schema_0_1_5.py` (feature 018) and earlier
0.1.4/0.1.3/0.1.2 files. Adds the 0.1.6-specific regression checks:
codebase-level `SCHEMA_VERSION = "0.1.6"`, two new additive top-level
fields (`preprocess_strategy_id`, `ocr_only_fallback_count`) emitted on
every run, fixed emission order AFTER feature 018's three fields and
before the closing brace, default values reflecting CPU-lane defaults
from `preprocessing/identifiers.py`.

T015 (US1) lands the `preprocess_strategy_id` slice; T019 (US2)
extends with cross-configuration checks; T024 (US3) extends with
`ocr_only_fallback_count` field-level checks.

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
    CPU_DEFAULT_PREPROCESS_STRATEGY,
)


def _make_minimal_run_summary(**overrides: Any) -> RunSummary:
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
# T015 / T004 / R-019.14: strict-pin SCHEMA_VERSION == "0.1.6"
# ---------------------------------------------------------------------------


def test_schema_version_is_0_1_6_codebase_level() -> None:
    """`SCHEMA_VERSION` is exactly `"0.1.6"` for every run of the new
    binary regardless of preset selection (per R-019.14 +
    `contracts/run-summary-schema.md` §1)."""
    assert timing.SCHEMA_VERSION == "0.1.6", (
        f"feature 019 must bump SCHEMA_VERSION from 0.1.5 to 0.1.6 "
        f"(got {timing.SCHEMA_VERSION!r})"
    )
    assert SCHEMA_VERSION == "0.1.6"


def test_run_summary_emits_0_1_6_in_json_line() -> None:
    """A serialized `run_summary` line carries `schema_version: "0.1.6"`
    on the wire."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert parsed["schema_version"] == "0.1.6"


# ---------------------------------------------------------------------------
# T015 / FR-008 / FR-010: preprocess_strategy_id emitted on every run
# ---------------------------------------------------------------------------


def test_preprocess_strategy_id_present_on_every_run() -> None:
    """Per FR-008 / FR-010 / contracts/run-summary-schema.md §3:
    `preprocess_strategy_id` is required on every run_summary line
    (absence is itself a regression signal)."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "preprocess_strategy_id" in parsed


def test_cpu_lane_default_preprocess_strategy_is_cpu_default() -> None:
    """Default RunSummary (no overrides) reflects CPU lane —
    `preprocess_strategy_id="cpu-default"` per R-019.3 / I-019.9."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert (
        parsed["preprocess_strategy_id"]
        == CPU_DEFAULT_PREPROCESS_STRATEGY
        == "cpu-default"
    )


@pytest.mark.parametrize(
    "strategy_id",
    ["ppstructurev3", "ocr-only-v1", "cpu-default", "stub-default"],
)
def test_preprocess_strategy_id_can_be_overridden(strategy_id: str) -> None:
    """A GPU run sets `preprocess_strategy_id` to the resolved preset
    name via the dataclass field — all four closed-vocabulary values
    flow through unchanged."""
    summary = _make_minimal_run_summary(preprocess_strategy_id=strategy_id)
    parsed = json.loads(summary.as_json_line())
    assert parsed["preprocess_strategy_id"] == strategy_id


# ---------------------------------------------------------------------------
# T024 / FR-007: ocr_only_fallback_count emitted on every run with default 0
# ---------------------------------------------------------------------------


def test_ocr_only_fallback_count_present_on_every_run() -> None:
    """Per FR-007 / Clarifications Q1: `ocr_only_fallback_count` is
    required on every run_summary line; default `0`."""
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    assert "ocr_only_fallback_count" in parsed
    assert parsed["ocr_only_fallback_count"] == 0


def test_ocr_only_fallback_count_is_integer() -> None:
    """`ocr_only_fallback_count` is an integer per FR-007 /
    contracts/run-summary-schema.md §3."""
    summary = _make_minimal_run_summary(ocr_only_fallback_count=3)
    parsed = json.loads(summary.as_json_line())
    assert parsed["ocr_only_fallback_count"] == 3
    assert isinstance(parsed["ocr_only_fallback_count"], int)


def test_ocr_only_fallback_count_zero_on_non_ocr_only_strategies() -> None:
    """On `preprocess_strategy_id != "ocr-only-v1"` runs the counter
    stays at 0 (no OCR-only attempts) per FR-007."""
    for sid in ["ppstructurev3", "cpu-default", "stub-default"]:
        summary = _make_minimal_run_summary(preprocess_strategy_id=sid)
        parsed = json.loads(summary.as_json_line())
        assert parsed["ocr_only_fallback_count"] == 0


# ---------------------------------------------------------------------------
# T015 / contracts/run-summary-schema.md §4: emission order is fixed
# ---------------------------------------------------------------------------


def test_feature_019_fields_emit_after_feature_018_fields_in_order() -> None:
    """Feature 019's two additive top-level fields land in fixed order
    AFTER feature 018's three fields and BEFORE the run_summary's
    terminating brace (contracts/run-summary-schema.md §4). The full
    eight-field run at the trailing edge is:

      preprocess_lane (014)
      module_set_id, det_rec_variant_id, ppstructure_modules_invoked (017)
      raster_profile_id, region_strategy_id, region_strategy_fallback_count (018)
      preprocess_strategy_id, ocr_only_fallback_count (019)
    """
    summary = _make_minimal_run_summary()
    parsed = json.loads(summary.as_json_line())
    keys = list(parsed.keys())
    pl_idx = keys.index("preprocess_lane")
    expected_tail = [
        "preprocess_lane",
        "module_set_id",
        "det_rec_variant_id",
        "ppstructure_modules_invoked",
        "raster_profile_id",
        "region_strategy_id",
        "region_strategy_fallback_count",
        "preprocess_strategy_id",
        "ocr_only_fallback_count",
    ]
    assert keys[pl_idx : pl_idx + len(expected_tail)] == expected_tail
    # Feature 019's two are the LAST two keys (no later additive yet)
    assert keys[-2:] == ["preprocess_strategy_id", "ocr_only_fallback_count"]


# ---------------------------------------------------------------------------
# Cross-preset stability: schema_version unchanged across preset selections
# ---------------------------------------------------------------------------


def test_schema_version_unchanged_across_preprocess_strategy_selections() -> None:
    """`schema_version` is `"0.1.6"` for every emission regardless of
    which preprocess_strategy the run used — fixed at the codebase
    level (R-019.14)."""
    for strategy_id in [
        "cpu-default",
        "stub-default",
        "ppstructurev3",
        "ocr-only-v1",
    ]:
        summary = _make_minimal_run_summary(preprocess_strategy_id=strategy_id)
        parsed = json.loads(summary.as_json_line())
        assert parsed["schema_version"] == "0.1.6", (
            f"schema_version must stay 0.1.6 across all preprocess_strategy "
            f"selections; got {parsed['schema_version']!r} for "
            f"preprocess_strategy_id={strategy_id!r}"
        )


# ---------------------------------------------------------------------------
# T019 (US2): cross-configuration distinct values
# ---------------------------------------------------------------------------


def test_distinct_preprocess_strategy_values_produce_distinct_run_summaries() -> None:
    """Two runs that differ only on the preprocess-strategy axis produce
    different `preprocess_strategy_id` values per SC-004."""
    s1 = _make_minimal_run_summary(preprocess_strategy_id="ppstructurev3")
    s2 = _make_minimal_run_summary(preprocess_strategy_id="ocr-only-v1")
    assert (
        json.loads(s1.as_json_line())["preprocess_strategy_id"]
        != json.loads(s2.as_json_line())["preprocess_strategy_id"]
    )


def test_identical_configurations_produce_identical_preprocess_strategy_id() -> None:
    """Two runs with the same configuration produce identical
    `preprocess_strategy_id` values per SC-004."""
    s1 = _make_minimal_run_summary(preprocess_strategy_id="ocr-only-v1")
    s2 = _make_minimal_run_summary(preprocess_strategy_id="ocr-only-v1")
    assert (
        json.loads(s1.as_json_line())["preprocess_strategy_id"]
        == json.loads(s2.as_json_line())["preprocess_strategy_id"]
    )
