"""Failure-path partial phase_timings emission test (T020 / Q5 / FP1 / FP2).

Exercises the corpus_run failure-path emission invariant directly via
`pipeline.timing` builder calls + RunSummary serialization. CPU-runnable
(no GPU / no real inference required) — the invariant under test is
shape semantics, not real-inference behavior.

Asserts:

- FP1: a `per_document` failure entry carries partial `phase_timings`
  (only the phases that completed before the failure) and partial
  `per_page_inference` (only the pages that completed inference).
- FP2: phases that did NOT run are absent from the dict, not zeroed
  or null.
- Both success and failure records can coexist in one RunSummary
  payload that round-trips through `as_json_line()`.
- The failure record retains `status: "failure"`, `failed_stage`,
  `exit_code`, `message` plus (when set) `gpu_lane_forced_abort`.
"""
from __future__ import annotations

import json

from ledgerlinc_ocr.pipeline.timing import (
    DocumentTimings,
    RunSummary,
    StageTiming,
    build_per_document_failure,
    build_per_document_success,
)


def test_t020_warm_corpus_partial_failure_phase_timings_round_trip() -> None:
    # Doc 0: full success — has all GPU one-time phases plus per-doc phases.
    doc0_phase_timings = {
        "paddle_import":   {"seconds": 1.42},
        "gpu_bind_probe":  {"seconds": 0.04},
        "engine_init":     {"seconds": 41.21},
        "rasterization":   {"seconds": 1.13},
        "artifact_write":  {"seconds": 0.05},
        "total":           {"seconds": 43.85},
    }
    doc0_per_page = [{"page": 1, "seconds": 8.43}, {"page": 2, "seconds": 7.91}]
    doc0 = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=DocumentTimings(stages={"preprocess": StageTiming(stage="preprocess")}),
        phase_timings=doc0_phase_timings,
        per_page_inference=doc0_per_page,
    )

    # Doc 1: failed mid-inference on page 2. Page 1 inference completed.
    # `rasterization` + `total` were captured up to the failure; `artifact_write`
    # never ran (key absent). GPU one-time phases are NOT on the failed doc.
    doc1_phase_timings = {
        "rasterization": {"seconds": 1.04},
        "total":         {"seconds": 9.32},
    }
    doc1_per_page = [{"page": 1, "seconds": 8.21}]
    doc1 = build_per_document_failure(
        document_id="inv_005_hard",
        folder="tests/stage1_vendor_identity/inv_005_hard",
        failed_stage="preprocess",
        exit_code=30,
        message="[ppstructurev3@gpu] document_id=inv_005_hard: predict raised on page 2",
        gpu_lane_forced_abort=True,
        phase_timings=doc1_phase_timings,
        per_page_inference=doc1_per_page,
    )

    # FP1 — failure record carries partial phase_timings + per_page_inference
    assert doc1["status"] == "failure"
    assert doc1["failed_stage"] == "preprocess"
    assert doc1["exit_code"] == 30
    assert doc1["gpu_lane_forced_abort"] is True
    assert "phase_timings" in doc1
    assert "per_page_inference" in doc1

    # FP2 — phases that did not run MUST be absent (not zeroed)
    assert set(doc1["phase_timings"].keys()) == {"rasterization", "total"}, (
        "FP2: artifact_write must be absent from a failed-mid-inference doc"
    )
    # GPU one-time phases must also be absent on the failed doc — they
    # only attach to the first successfully processed entry per FR-015.
    forbidden = {"paddle_import", "gpu_bind_probe", "engine_init", "warmup"}
    assert forbidden.isdisjoint(doc1["phase_timings"].keys()), (
        f"FR-015: GPU one-time phases must not appear on failed doc; "
        f"got {forbidden & set(doc1['phase_timings'].keys())}"
    )
    # Page 2 absent (failed before timing capture)
    assert [p["page"] for p in doc1["per_page_inference"]] == [1]

    # Round-trip through RunSummary as_json_line()
    summary = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@gpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=2,
        documents_succeeded=1,
        documents_failed=1,
        per_document=[doc0, doc1],
        preprocess_lane="gpu0",
    )
    line = summary.as_json_line()
    parsed = json.loads(line)
    assert parsed["schema_version"] == "0.1.4"  # feature 017: 0.1.3 → 0.1.4 (additive top-level fields)
    assert parsed["documents_succeeded"] == 1
    assert parsed["documents_failed"] == 1
    assert parsed["per_document"][0]["status"] == "success"
    assert parsed["per_document"][1]["status"] == "failure"
    # FP1 in serialized form
    assert "phase_timings" in parsed["per_document"][1]
    assert "rasterization" in parsed["per_document"][1]["phase_timings"]
    assert "artifact_write" not in parsed["per_document"][1]["phase_timings"]
    # FP1: per_page_inference round-trip
    assert parsed["per_document"][1]["per_page_inference"] == [{"page": 1, "seconds": 8.21}]
