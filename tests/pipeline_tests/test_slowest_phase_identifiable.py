"""Slowest-phase-identifiable test (T026 / SC-005).

Asserts that the data shape emitted on a successful run supports the
SC-005 reader-experience criterion: the slowest phase can be identified
from the run_summary line alone, without rerunning the pipeline.

This is a smoke-grade assertion on the data shape — sorting
`phase_timings.items()` by `seconds` desc must produce a deterministic
ranking with positive values. It does NOT assert which phase is
actually slowest (that depends on hardware).
"""
from __future__ import annotations

from ledgerlinc_ocr.pipeline.timing import (
    DocumentTimings,
    StageTiming,
    build_per_document_success,
)


def test_t026_phase_timings_supports_slowest_phase_ranking() -> None:
    phase_timings = {
        "paddle_import":   {"seconds": 1.42},
        "gpu_bind_probe":  {"seconds": 0.04},
        "engine_init":     {"seconds": 41.21},
        "rasterization":   {"seconds": 1.13},
        "artifact_write":  {"seconds": 0.05},
        "total":           {"seconds": 43.85},
    }
    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=DocumentTimings(stages={"preprocess": StageTiming(stage="preprocess")}),
        phase_timings=phase_timings,
    )

    # Exclude `total` from the slowest-named-phase ranking — it's the
    # outer wall-clock and would always dominate.
    candidates = {
        name: rec["seconds"]
        for name, rec in record["phase_timings"].items()
        if name != "total"
    }
    ranked = sorted(candidates.items(), key=lambda kv: -kv[1])

    assert len(ranked) >= 1, "phase_timings must contain at least one named phase"
    slowest_name, slowest_seconds = ranked[0]
    assert slowest_seconds > 0, "slowest phase seconds must be positive"
    # In this synthetic example, engine_init is the dominant phase (the
    # real GPU run is expected to follow the same pattern post-T008
    # before subsequent latency optimizations).
    assert slowest_name == "engine_init"
    # Ranking is deterministic: same input → same output.
    ranked_again = sorted(candidates.items(), key=lambda kv: -kv[1])
    assert ranked == ranked_again
