"""Unit tests for timing capture and run-summary serialization.

Covers Spec FR-027; Research R-009 / R-015.
"""
from __future__ import annotations

import io
import json
import time

import pytest

from dartwing_ocr.pipeline.timing import (
    SCHEMA_VERSION,
    DocumentTimings,
    RunSummary,
    StageTiming,
    build_per_document_failure,
    build_per_document_success,
    emit_run_summary,
    measure_phase,
    measure_total,
)


# ---------------------------------------------------------------------------
# StageTiming nanosecond capture and seconds serialization
# ---------------------------------------------------------------------------

def test_measure_total_records_entry_to_exit_ns():
    timing = StageTiming(stage="preprocess")
    with measure_total(timing):
        time.sleep(0.001)  # at least 1ms
    assert timing.total_ns >= 1_000_000


def test_measure_phase_accumulates_ns_under_phase_key():
    timing = StageTiming(stage="preprocess")
    with measure_phase(timing, "rasterize"):
        time.sleep(0.001)
    with measure_phase(timing, "rasterize"):
        time.sleep(0.001)
    assert timing.phases_ns["rasterize"] >= 2_000_000


def test_to_seconds_map_six_decimal_rounding_and_phase_suffix():
    timing = StageTiming(
        stage="preprocess",
        phases_ns={"rasterize": 123_456_789, "infer": 1_000_000_000},
        total_ns=2_500_000_000,
    )
    out = timing.to_seconds_map()
    assert out["rasterize_seconds"] == round(123_456_789 / 1e9, 6)
    assert out["infer_seconds"] == pytest.approx(1.0)
    assert out["total_seconds"] == pytest.approx(2.5)


def test_phase_keys_omitted_when_not_measured():
    """R-009 phase-key absence policy: absent != 0.0."""
    timing = StageTiming(stage="extract", total_ns=1_000_000_000)
    out = timing.to_seconds_map()
    # No phase ever recorded -> only total_seconds present.
    assert "infer_seconds" not in out
    assert "write_seconds" not in out
    assert out["total_seconds"] == pytest.approx(1.0)


def test_measure_total_still_records_when_block_raises():
    timing = StageTiming(stage="preprocess")
    with pytest.raises(RuntimeError):
        with measure_total(timing):
            time.sleep(0.001)
            raise RuntimeError("simulated stage failure")
    assert timing.total_ns > 0


# ---------------------------------------------------------------------------
# DocumentTimings (per-document aggregation)
# ---------------------------------------------------------------------------

def test_document_timings_get_or_create_idempotent():
    docs = DocumentTimings()
    a = docs.get_or_create("preprocess")
    b = docs.get_or_create("preprocess")
    assert a is b


def test_document_timings_to_summary_dict_only_includes_observed_stages():
    docs = DocumentTimings()
    docs.get_or_create("preprocess").total_ns = 1_000_000_000
    out = docs.to_summary_dict()
    assert "preprocess" in out
    assert "extract" not in out


# ---------------------------------------------------------------------------
# RunSummary serialization (R-009 schema)
# ---------------------------------------------------------------------------

def test_run_summary_minimal_shape():
    s = RunSummary(
        stack_preset=None,
        resolved_profiles={
            "preprocess": "ppstructurev3@cpu",
            "extract": "ollama@gpu",
            "routing": "rules@cpu",
            "final_payload": "assembler@cpu",
        },
        execution_slice={"start_at": "preprocess", "stop_after": "final_payload"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
    payload = s.to_dict()
    assert payload["kind"] == "run_summary"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["stack_preset"] is None
    assert payload["execution_slice"] == {
        "start_at": "preprocess",
        "stop_after": "final_payload",
    }
    assert payload["per_document"] == []
    assert payload["profile_initialization_seconds"] == {}


def test_run_summary_records_stack_preset_verbatim():
    s = RunSummary(
        stack_preset="cloud-workstation",
        resolved_profiles={"preprocess": "ppstructurev3@cpu",
                           "extract": "ensemble@workstation",
                           "routing": "rules@cpu",
                           "final_payload": "assembler@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "final_payload"},
        on_failure="continue",
        documents_total=1,
        documents_succeeded=0,
        documents_failed=1,
    )
    assert s.to_dict()["stack_preset"] == "cloud-workstation"


def test_emit_run_summary_writes_one_json_line(tmp_path):
    """R-009: run-summary is a JSON-Lines record (single line, no array wrapper)."""
    s = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "stub", "extract": "stub", "routing": "stub", "final_payload": "stub"},
        execution_slice={"start_at": "preprocess", "stop_after": "final_payload"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
    buf = io.StringIO()
    emit_run_summary(s, stream=buf)
    output = buf.getvalue()
    assert output.endswith("\n")
    # Exactly one line.
    assert output.count("\n") == 1
    parsed = json.loads(output.strip())
    assert parsed["kind"] == "run_summary"


def test_per_document_success_record_shape():
    docs = DocumentTimings()
    docs.get_or_create("preprocess").total_ns = 1_000_000_000
    rec = build_per_document_success(
        document_id="inv_001",
        folder="/tmp/inv_001_easy",
        timings=docs,
    )
    assert rec["status"] == "success"
    assert rec["document_id"] == "inv_001"
    assert rec["stages"]["preprocess"]["total_seconds"] == pytest.approx(1.0)


def test_per_document_failure_record_shape_omits_stages_when_none():
    rec = build_per_document_failure(
        document_id="inv_002",
        folder="/tmp/inv_002_easy",
        failed_stage="preprocess",
        exit_code=20,
        message="simulated failure",
    )
    assert rec["status"] == "failure"
    assert rec["failed_stage"] == "preprocess"
    assert rec["exit_code"] == 20
    assert "stages" not in rec


def test_per_document_failure_record_includes_partial_timings_when_present():
    docs = DocumentTimings()
    docs.get_or_create("preprocess").total_ns = 500_000_000
    rec = build_per_document_failure(
        document_id="inv_003",
        folder="/tmp/inv_003_hard",
        failed_stage="extract",
        exit_code=20,
        message="extract crashed",
        timings=docs,
    )
    assert "stages" in rec
    assert rec["stages"]["preprocess"]["total_seconds"] == pytest.approx(0.5)
