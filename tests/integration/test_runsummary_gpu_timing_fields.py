"""Run-summary GPU timing field tests (T025, FR-022, R-014.6).

CPU-side coverage (runnable on default CI without a GPU):

- `SCHEMA_VERSION == "0.1.1"` (T027).
- `RunSummary.to_dict()` always emits `preprocess_lane` (default `"cpu"`)
  and accepts `"gpu0"` when constructed with the GPU lane.
- `build_per_document_failure(...)` accepts the optional
  `gpu_lane_forced_abort` keyword (T024 / CF9): absent by default,
  present-and-true when set.
- `take_gpu_inference_seconds()` drains the accumulated GPU inference
  time and resets the counter (T030).

The full GPU end-to-end scenario (T025: a real warm-corpus GPU run that
asserts `preprocess_lane == "gpu0"`, `gpu_init_seconds` on
`per_document[0]` only, `gpu_inference_seconds` on every success record,
and the classify-once spy / VT6 assertion) is exercised on real GPU
hosts only via separate integration suites gated by the conftest `gpu`
marker hook (FR-019). The classify-once spy logic is verified at the
unit level by `tests/unit/test_preflight_classifier.py`; no dead
`@pytest.mark.gpu` placeholder is kept in this file.
"""
from __future__ import annotations

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


