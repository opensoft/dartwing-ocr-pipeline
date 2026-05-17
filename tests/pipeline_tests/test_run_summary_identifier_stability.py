"""Feature 017 (T027 / US3 / SC-003 / Plan §I-8): CPU-safe
identifier-stability test.

Per SC-003: two consecutive CPU runs with identical inputs produce
identical values for all three new top-level fields. Plus a third run
with a flag combination that warn-and-proceeds on CPU
(`--module-set=reduced-v1`); the three fields STILL match the first
two runs (CPU lane's identifiers reflect profile defaults regardless
of flag values per Plan §I-8).
"""
from __future__ import annotations

import json

from dartwing_ocr.pipeline.timing import RunSummary


def test_two_cpu_runs_emit_identical_identifier_fields() -> None:
    """Two RunSummary constructions with identical inputs emit
    identical values for the three additive fields (SC-003
    within-configuration stability)."""
    run1 = _make_minimal_summary()
    run2 = _make_minimal_summary()
    parsed1 = json.loads(run1.as_json_line())
    parsed2 = json.loads(run2.as_json_line())
    for field in ("module_set_id", "det_rec_variant_id", "ppstructure_modules_invoked"):
        assert parsed1[field] == parsed2[field], (
            f"two identical CPU runs differ on {field}: "
            f"{parsed1[field]!r} vs {parsed2[field]!r}"
        )


def test_warn_and_proceed_run_emits_same_identifiers_as_no_flag_run() -> None:
    """Per Plan §I-8: a CPU run where the operator sets `--module-set`
    or `--det-rec-variant` (warn-and-proceed branch) MUST emit the same
    identifier values as a no-flag run — the warn-and-proceed branch
    drops the resolved values, so CPU/stub identity-preset defaults
    flow through unchanged. Asserts at the RunSummary level (the CLI
    integration test in `test_presets_cpu_warn_and_proceed.py` covers
    the upstream wiring)."""
    no_flag_run = _make_minimal_summary()
    # Simulating a warn-and-proceed CPU run: the CLI dropped the resolved
    # preset value, so RunSummary's defaults reach to_dict unchanged.
    warn_and_proceed_run = _make_minimal_summary()
    # NOT setting module_set_id/det_rec_variant_id explicitly here matches
    # the actual CLI behavior: cpu/stub lane writes the dataclass defaults
    p1 = json.loads(no_flag_run.as_json_line())
    p2 = json.loads(warn_and_proceed_run.as_json_line())
    assert p1["module_set_id"] == p2["module_set_id"] == "cpu-default"
    assert p1["det_rec_variant_id"] == p2["det_rec_variant_id"] == "cpu-default"
    assert p1["ppstructure_modules_invoked"] == p2["ppstructure_modules_invoked"] == []


def test_different_module_set_produces_different_module_set_id() -> None:
    """SC-003: two runs that differ on the module set have different
    `module_set_id` values; `det_rec_variant_id` unchanged when only
    that axis varies."""
    legacy_run = _make_minimal_summary()
    legacy_run.module_set_id = "legacy"
    legacy_run.det_rec_variant_id = "legacy"

    reduced_run = _make_minimal_summary()
    reduced_run.module_set_id = "reduced-v1"
    reduced_run.det_rec_variant_id = "legacy"  # same det/rec axis

    p_legacy = json.loads(legacy_run.as_json_line())
    p_reduced = json.loads(reduced_run.as_json_line())

    # Different on the varied axis
    assert p_legacy["module_set_id"] != p_reduced["module_set_id"]
    assert p_legacy["module_set_id"] == "legacy"
    assert p_reduced["module_set_id"] == "reduced-v1"
    # Identical on the unchanged axis
    assert p_legacy["det_rec_variant_id"] == p_reduced["det_rec_variant_id"] == "legacy"


def test_different_det_rec_variant_produces_different_det_rec_variant_id() -> None:
    """SC-003 mirror: two runs that differ on det/rec variant have
    different `det_rec_variant_id`; `module_set_id` unchanged."""
    legacy_dr = _make_minimal_summary()
    legacy_dr.module_set_id = "legacy"
    legacy_dr.det_rec_variant_id = "legacy"

    mobile_dr = _make_minimal_summary()
    mobile_dr.module_set_id = "legacy"
    mobile_dr.det_rec_variant_id = "ppocrv5-mobile"

    p_legacy = json.loads(legacy_dr.as_json_line())
    p_mobile = json.loads(mobile_dr.as_json_line())

    assert p_legacy["det_rec_variant_id"] != p_mobile["det_rec_variant_id"]
    assert p_legacy["module_set_id"] == p_mobile["module_set_id"] == "legacy"


def test_same_configuration_on_both_axes_produces_identical_identifiers() -> None:
    """SC-003 third clause: two runs with the same configuration on
    both axes have identical values for both fields."""
    run1 = _make_minimal_summary()
    run1.module_set_id = "reduced-v1"
    run1.det_rec_variant_id = "ppocrv5-mobile"

    run2 = _make_minimal_summary()
    run2.module_set_id = "reduced-v1"
    run2.det_rec_variant_id = "ppocrv5-mobile"

    p1 = json.loads(run1.as_json_line())
    p2 = json.loads(run2.as_json_line())
    assert p1["module_set_id"] == p2["module_set_id"] == "reduced-v1"
    assert p1["det_rec_variant_id"] == p2["det_rec_variant_id"] == "ppocrv5-mobile"


def _make_minimal_summary() -> RunSummary:
    return RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
