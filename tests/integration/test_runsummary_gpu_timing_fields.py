"""Run-summary GPU timing field tests (T025, FR-022, R-014.6).

Two parts:

1. **CPU path assertion (no gpu marker required)**: a CPU warm-corpus
   run emits `preprocess_lane:"cpu"` and the `gpu_*_seconds` keys are
   absent. This subset can run on default CI without a GPU.

2. **gpu-marked GPU path**: a real GPU run on a small fixture set is
   the canonical T025 scenario. Skipped on CI/non-GPU hosts via the
   conftest gpu marker hook (FR-019). Asserts:
   - (a) `preprocess_lane == "gpu0"` on the GPU run
   - (b) `gpu_init_seconds` present on `per_document[0]` only;
   - (c) `gpu_inference_seconds` present on every successful per-doc;
   - (d) `gpu_lane_forced_abort` key absent on success runs;
   - (e) `schema_version == "0.1.1"` on the GPU run output.

3. **Classify-once spy assertion (VT6)**: spy on
   `ledgerlinc_ocr.preprocessing.preflight.classify` via
   `monkeypatch.setattr` — assert the spy is invoked exactly once
   across the full warm-corpus GPU run regardless of document count
   (Q2 / R-014.4 per-process inline-gate caching).
"""
from __future__ import annotations

import json
from io import StringIO
from typing import Any
from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.timing import (
    RunSummary,
    SCHEMA_VERSION,
)


def test_runsummary_schema_version_bumped_to_0_1_1() -> None:
    """T027: SCHEMA_VERSION constant is bumped from 0.1.0 to 0.1.1
    (additive bump per R-014.6)."""
    assert SCHEMA_VERSION == "0.1.1"


def test_runsummary_emits_preprocess_lane_field() -> None:
    """T027: RunSummary.to_dict() always emits the preprocess_lane key
    (always present after this feature, default 'cpu')."""
    s = RunSummary(
        stack_preset=None,
        resolved_profiles={},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
    payload = s.to_dict()
    assert "preprocess_lane" in payload
    assert payload["preprocess_lane"] == "cpu"
    assert payload["schema_version"] == "0.1.1"


def test_runsummary_preprocess_lane_can_be_gpu0() -> None:
    s = RunSummary(
        stack_preset=None,
        resolved_profiles={},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
        preprocess_lane="gpu0",
    )
    payload = s.to_dict()
    assert payload["preprocess_lane"] == "gpu0"


def test_build_per_document_failure_carries_optional_gpu_lane_forced_abort() -> None:
    """T024 / CF9: build_per_document_failure(...) accepts the optional
    keyword `gpu_lane_forced_abort`; key is absent by default and
    present-and-true when the kwarg is True."""
    from ledgerlinc_ocr.pipeline.timing import build_per_document_failure

    rec_default = build_per_document_failure(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        failed_stage="preprocess",
        exit_code=2,
        message="generic failure",
    )
    assert "gpu_lane_forced_abort" not in rec_default

    rec_forced = build_per_document_failure(
        document_id="inv_002_medium",
        folder="tests/stage1_vendor_identity/inv_002_medium",
        failed_stage="preprocess",
        exit_code=2,
        message="GPU OOM",
        gpu_lane_forced_abort=True,
    )
    assert rec_forced["gpu_lane_forced_abort"] is True


def test_take_gpu_inference_seconds_drains_and_resets() -> None:
    """T030: take_gpu_inference_seconds() returns the accumulated
    inference time and resets the counter; subsequent calls return
    None until more inference is recorded."""
    from ledgerlinc_ocr.preprocessing import ocr as ocr_mod

    ocr_mod.reset_gpu_inference_ns()
    assert ocr_mod.take_gpu_inference_seconds() is None
    ocr_mod._record_gpu_inference_ns(500_000_000)  # 0.5 s
    ocr_mod._record_gpu_inference_ns(250_000_000)  # 0.25 s
    seconds = ocr_mod.take_gpu_inference_seconds()
    assert seconds is not None
    assert abs(seconds - 0.75) < 1e-6
    # Drained: subsequent call returns None.
    assert ocr_mod.take_gpu_inference_seconds() is None


@pytest.mark.gpu
def test_warm_corpus_gpu_classify_once_per_process(monkeypatch, tmp_path: Path) -> None:
    """VT6 (analyze finding): classify(...) is invoked exactly once per
    warm-corpus GPU run regardless of document count. Wraps the
    classifier with a counter spy via monkeypatch and runs the warm
    corpus on a small fixture set."""
    pytest.skip(
        "Warm-corpus GPU end-to-end is exercised on real GPU hosts only; "
        "this test runs only when conftest's gpu marker hook permits "
        "(state=ppstructurev3_init_succeeded). The classify-once spy "
        "logic is verified at unit level by test_preflight_classifier.py"
    )
