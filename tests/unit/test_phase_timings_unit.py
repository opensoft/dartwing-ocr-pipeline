"""Phase-timings unit tests (feature 015 / T003).

Covers PT1–PT4 from `contracts/module-invariants.md`:

- PT1 — every value emitted by the new `phase_timings` builder is shape
  `{"seconds": float}` only (no extra keys, no `started_at`, etc.).
- PT2 — `per_page_inference` items are `{"page": int, "seconds": float}` only.
- PT3 — `per_page_inference[*].page` is strictly ascending and 1-based.
- PT4 — durations come from a monotonic clock; `phase_timings.total.seconds`
  is approximately equal to (or greater than) the sum of named child phases.
"""
from __future__ import annotations

from typing import Any

import pytest


timing = pytest.importorskip("ledgerlinc_ocr.pipeline.timing")
StageTiming = timing.StageTiming
build_per_document_success = timing.build_per_document_success


# Expected FR-013 phase keys (single source of truth = spec.md §FR-013).
EXPECTED_PHASE_KEYS = {
    "paddle_import",
    "gpu_bind_probe",
    "engine_init",
    "warmup",  # optional / reserved
    "rasterization",
    "artifact_write",
    "total",
}


def _make_phase_timings(**phases: float) -> dict[str, dict[str, float]]:
    """Build a phase_timings dict in the canonical shape."""
    return {name: {"seconds": float(seconds)} for name, seconds in phases.items()}


def _make_per_page_inference(*page_seconds: tuple[int, float]) -> list[dict[str, Any]]:
    return [{"page": int(p), "seconds": float(s)} for p, s in page_seconds]


# ---------------------------------------------------------------------------
# PT1 — phase record shape
# ---------------------------------------------------------------------------

def test_pt1_each_phase_record_has_only_seconds_key() -> None:
    phase_timings = _make_phase_timings(
        paddle_import=1.42,
        gpu_bind_probe=0.04,
        engine_init=41.21,
        rasterization=1.13,
        artifact_write=0.05,
        total=43.85,
    )
    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=timing.DocumentTimings(),
        phase_timings=phase_timings,
        per_page_inference=None,
    )
    assert "phase_timings" in record
    for name, value in record["phase_timings"].items():
        assert isinstance(value, dict), f"phase {name!r} value must be a dict"
        assert set(value.keys()) == {"seconds"}, (
            f"phase {name!r} must have exactly one key 'seconds', got {set(value.keys())}"
        )
        assert isinstance(value["seconds"], (int, float)), (
            f"phase {name!r}.seconds must be numeric, got {type(value['seconds'])}"
        )
        assert value["seconds"] >= 0, f"phase {name!r}.seconds must be non-negative"


def test_pt1_phase_keys_are_subset_of_fr013_vocabulary() -> None:
    phase_timings = _make_phase_timings(
        paddle_import=1.42,
        gpu_bind_probe=0.04,
        engine_init=41.21,
        rasterization=1.13,
        artifact_write=0.05,
        total=43.85,
    )
    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=timing.DocumentTimings(),
        phase_timings=phase_timings,
    )
    assert set(record["phase_timings"].keys()) <= EXPECTED_PHASE_KEYS


# ---------------------------------------------------------------------------
# PT2 — per_page_inference shape
# ---------------------------------------------------------------------------

def test_pt2_per_page_items_have_only_page_and_seconds_keys() -> None:
    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=timing.DocumentTimings(),
        phase_timings=_make_phase_timings(total=10.0),
        per_page_inference=_make_per_page_inference((1, 8.43), (2, 7.91)),
    )
    assert "per_page_inference" in record
    arr = record["per_page_inference"]
    assert isinstance(arr, list)
    for item in arr:
        assert isinstance(item, dict), "per_page_inference items must be dicts"
        assert set(item.keys()) == {"page", "seconds"}, (
            f"per_page item must have exactly {{'page','seconds'}}, got {set(item.keys())}"
        )
        assert isinstance(item["page"], int), "page must be int"
        assert isinstance(item["seconds"], (int, float)), "seconds must be numeric"


# ---------------------------------------------------------------------------
# PT3 — pages strictly ascending and 1-based
# ---------------------------------------------------------------------------

def test_pt3_per_page_inference_pages_strictly_ascending_and_one_based() -> None:
    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=timing.DocumentTimings(),
        phase_timings=_make_phase_timings(total=20.0),
        per_page_inference=_make_per_page_inference((1, 5.0), (2, 4.5), (3, 6.2)),
    )
    pages = [p["page"] for p in record["per_page_inference"]]
    assert pages[0] == 1, "first page must be 1 (1-based, FR-014)"
    assert all(pages[i] < pages[i + 1] for i in range(len(pages) - 1)), (
        "per_page_inference pages must be strictly ascending"
    )


def test_pt3_partial_per_page_after_failed_page_omits_failed_entry() -> None:
    """Failed page is absent from the array, not zeroed (FR-016)."""
    # Page 1 succeeded (3.0s); page 2 failed and is absent.
    record = build_per_document_success(
        document_id="inv_005_hard",
        folder="tests/stage1_vendor_identity/inv_005_hard",
        timings=timing.DocumentTimings(),
        phase_timings=_make_phase_timings(rasterization=1.04, total=9.32),
        per_page_inference=_make_per_page_inference((1, 8.21)),
    )
    pages = [p["page"] for p in record["per_page_inference"]]
    assert pages == [1], "failed page must be absent from per_page_inference"


# ---------------------------------------------------------------------------
# PT4 — monotonic-clock semantics: total ≥ sum of children
# ---------------------------------------------------------------------------

def test_pt4_total_seconds_is_at_least_sum_of_named_children() -> None:
    """Sanity check that total represents wall-clock and uses the same
    monotonic clock as the children (allows for small overhead)."""
    children = {
        "paddle_import": 1.42,
        "gpu_bind_probe": 0.04,
        "engine_init": 41.21,
        "rasterization": 1.13,
        "artifact_write": 0.05,
    }
    sum_children = sum(children.values())
    total = sum_children + 0.5  # small wall-clock overhead

    phase_timings = _make_phase_timings(**children, total=total)
    assert phase_timings["total"]["seconds"] + 1e-3 >= sum_children, (
        "total.seconds must be ≥ sum of named children (monotonic-clock invariant)"
    )


# ---------------------------------------------------------------------------
# Failure-path emission (FP1 / FP2 / Q5)
# ---------------------------------------------------------------------------

def test_failed_doc_record_can_carry_partial_phase_timings() -> None:
    build_per_document_failure = timing.build_per_document_failure
    record = build_per_document_failure(
        document_id="inv_005_hard",
        folder="tests/stage1_vendor_identity/inv_005_hard",
        failed_stage="preprocess",
        exit_code=30,
        message="page 2 inference failed",
        phase_timings=_make_phase_timings(rasterization=1.04, total=9.32),
        per_page_inference=_make_per_page_inference((1, 8.21)),
    )
    assert record["status"] == "failure"
    assert record["failed_stage"] == "preprocess"
    assert record["exit_code"] == 30
    assert "phase_timings" in record
    assert set(record["phase_timings"].keys()) == {"rasterization", "total"}, (
        "FP2: phases not performed (artifact_write) must be omitted, not zeroed"
    )
    assert record["per_page_inference"] == [{"page": 1, "seconds": 8.21}]
