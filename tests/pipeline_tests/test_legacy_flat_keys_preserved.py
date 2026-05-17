"""Legacy flat keys back-compat regression test (T036 / FR-014 / R-015.4).

Asserts that feature 014's flat keys on `stages.preprocess` are still
emitted alongside feature 015's structured `phase_timings` block, so
0.1.1 consumers continue to read 0.1.2 output unchanged.

Specifically: a successful per_document entry built by
`build_per_document_success(...)` with a populated StageTiming MUST
contain `stages.preprocess.total_seconds`, AND when the caller
attaches `gpu_init_seconds` / `gpu_inference_seconds` (corpus_run.py
does this on the GPU lane), those flat keys MUST appear too.
"""
from __future__ import annotations

import pytest

from dartwing_ocr.pipeline.timing import (
    DocumentTimings,
    StageTiming,
    build_per_document_success,
)


def test_t036_legacy_flat_total_seconds_preserved_in_0_1_2() -> None:
    """Feature 014's `stages.preprocess.total_seconds` flat key MUST
    persist alongside feature 015's `phase_timings.total.seconds`."""
    st = StageTiming(stage="preprocess")
    st.add_phase("rasterization", 1_130_000_000)
    st.add_phase("artifact_write", 50_000_000)
    st.total_ns = 102_710_000_000

    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=DocumentTimings(stages={"preprocess": st}),
        phase_timings={
            "rasterization": {"seconds": 1.13},
            "artifact_write": {"seconds": 0.05},
            "total": {"seconds": 102.71},
        },
    )

    # Legacy flat form
    assert "stages" in record
    assert "preprocess" in record["stages"]
    preprocess_stage = record["stages"]["preprocess"]
    assert "total_seconds" in preprocess_stage, (
        "back-compat: stages.preprocess.total_seconds MUST persist in 0.1.2"
    )
    assert preprocess_stage["total_seconds"] == pytest.approx(102.71)

    # New structured form
    assert "phase_timings" in record
    assert record["phase_timings"]["total"]["seconds"] == pytest.approx(102.71)

    # Both forms coexist on the same record (FR-014 additive-only rule).
    assert "phase_timings" in record and "stages" in record


def test_t036_gpu_init_and_inference_seconds_can_coexist_with_phase_timings() -> None:
    """Corpus_run attaches `gpu_init_seconds` and `gpu_inference_seconds`
    to `stages.preprocess` AND populates `phase_timings.engine_init`
    + builds `per_page_inference`. Both forms MUST coexist."""
    st = StageTiming(stage="preprocess")
    st.total_ns = 102_710_000_000

    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=DocumentTimings(stages={"preprocess": st}),
        phase_timings={
            "engine_init": {"seconds": 41.21},
            "total": {"seconds": 102.71},
        },
        per_page_inference=[{"page": 1, "seconds": 8.43}],
    )

    # Manually attach legacy flat keys (mirrors corpus_run.py's emission).
    record["stages"]["preprocess"]["gpu_init_seconds"] = 41.21
    record["stages"]["preprocess"]["gpu_inference_seconds"] = 8.43

    # Both forms present
    assert record["stages"]["preprocess"]["gpu_init_seconds"] == pytest.approx(41.21)
    assert record["phase_timings"]["engine_init"]["seconds"] == pytest.approx(41.21)
    assert record["stages"]["preprocess"]["gpu_inference_seconds"] == pytest.approx(8.43)
    assert record["per_page_inference"][0]["seconds"] == pytest.approx(8.43)
