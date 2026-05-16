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

from dartwing_ocr.pipeline.timing import (
    RunSummary,
    SCHEMA_VERSION,
)


def test_runsummary_schema_version_bumped_to_at_least_0_1_1() -> None:
    """T027: SCHEMA_VERSION was bumped from 0.1.0 to 0.1.1 (R-014.6).
    Feature 015 (T011 / R-015.4) further bumped 0.1.1 → 0.1.2 additively;
    consumers built against 0.1.1 continue to read 0.1.2 unchanged. The
    invariant this test guards is "≥ 0.1.1," not exact equality."""
    parts = tuple(int(p) for p in SCHEMA_VERSION.split("."))
    assert parts >= (0, 1, 1), f"schema_version regressed below 0.1.1: {SCHEMA_VERSION!r}"


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
    # Feature 015: schema_version bumped 0.1.1 → 0.1.2; assert ≥ 0.1.1.
    parts = tuple(int(p) for p in payload["schema_version"].split("."))
    assert parts >= (0, 1, 1)


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
    from dartwing_ocr.pipeline.timing import build_per_document_failure

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
    None until more inference is recorded.

    Feature 015 (R-015.3 / T009): the accumulator is now a list of
    (page_number, ns) tuples. `_record_gpu_inference_ns` requires a
    page number argument. The legacy `take_gpu_inference_seconds()`
    helper is preserved as a back-compat wrapper that sums seconds."""
    from dartwing_ocr.preprocessing import ocr as ocr_mod

    ocr_mod.reset_gpu_inference_ns()
    assert ocr_mod.take_gpu_inference_seconds() is None
    ocr_mod._record_gpu_inference_ns(1, 500_000_000)  # page 1, 0.5 s
    ocr_mod._record_gpu_inference_ns(2, 250_000_000)  # page 2, 0.25 s
    seconds = ocr_mod.take_gpu_inference_seconds()
    assert seconds is not None
    assert abs(seconds - 0.75) < 1e-6
    # Drained: subsequent call returns None.
    assert ocr_mod.take_gpu_inference_seconds() is None


def test_take_gpu_inference_per_page_returns_tuples() -> None:
    """Feature 015 (R-015.3 / T009): the new `take_gpu_inference_per_page()`
    helper returns per-page (page, seconds) tuples and resets."""
    from dartwing_ocr.preprocessing import ocr as ocr_mod

    ocr_mod.reset_gpu_inference_ns()
    assert ocr_mod.take_gpu_inference_per_page() is None
    ocr_mod._record_gpu_inference_ns(1, 500_000_000)
    ocr_mod._record_gpu_inference_ns(2, 250_000_000)
    drained = ocr_mod.take_gpu_inference_per_page()
    assert drained == [(1, 0.5), (2, 0.25)]
    assert ocr_mod.take_gpu_inference_per_page() is None


def test_take_gpu_inference_per_page_sums_duplicate_pages() -> None:
    """Feature 018 fallback may infer page 1 twice; emit one sorted page entry."""
    from dartwing_ocr.preprocessing import ocr as ocr_mod

    ocr_mod.reset_gpu_inference_ns()
    ocr_mod._record_gpu_inference_ns(1, 500_000_000)
    ocr_mod._record_gpu_inference_ns(1, 250_000_000)
    ocr_mod._record_gpu_inference_ns(2, 125_000_000)
    drained = ocr_mod.take_gpu_inference_per_page()
    assert drained == [(1, 0.75), (2, 0.125)]
    assert ocr_mod.take_gpu_inference_per_page() is None

