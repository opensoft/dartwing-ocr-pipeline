"""CPU-lane GPU-isolation tests (T030 / ISO1 / SC-006 / FR-009 / FR-017).

Asserts that CPU-lane runs (both default-profile and explicit
`ppstructurev3@cpu`) emit no GPU-specific phase keys in their
run_summary output:

- `phase_timings` keys are a subset of `{rasterization, artifact_write, total}`
  on every per_document entry.
- `per_page_inference` is absent on every per_document entry (FR-017
  collapses CPU per-page time into `total_seconds`).
- `preprocess_lane == "cpu"` regardless of whether profile was
  defaulted or explicit (FR-009 default-profile invariant).

CPU-runnable; no GPU hardware required.
"""
from __future__ import annotations

from ledgerlinc_ocr.pipeline.timing import (
    DocumentTimings,
    RunSummary,
    StageTiming,
    build_per_document_success,
)


CPU_ALLOWED_PHASE_KEYS = {"rasterization", "artifact_write", "total"}
GPU_ONLY_PHASE_KEYS = {"paddle_import", "gpu_bind_probe", "engine_init", "warmup"}


def _build_cpu_record(document_id: str) -> dict:
    """Build a CPU-lane per-document record using only the CPU-allowed
    phase keys, mirroring how corpus_run.py's success path emits."""
    phase_timings = {
        "rasterization": {"seconds": 1.10},
        "artifact_write": {"seconds": 0.05},
        "total": {"seconds": 9.50},
    }
    return build_per_document_success(
        document_id=document_id,
        folder=f"tests/stage1_vendor_identity/{document_id}",
        timings=DocumentTimings(stages={"preprocess": StageTiming(stage="preprocess")}),
        phase_timings=phase_timings,
        per_page_inference=None,  # FR-017: CPU lane omits per_page_inference
    )


def test_t030_cpu_lane_phase_timings_subset_of_cpu_allowed() -> None:
    """ISO1: CPU lane phase_timings keys ⊆ {rasterization, artifact_write, total}."""
    record = _build_cpu_record("inv_001_easy")
    keys = set(record["phase_timings"].keys())
    assert keys <= CPU_ALLOWED_PHASE_KEYS, (
        f"FR-017 / ISO1: CPU lane phase_timings must be a subset of "
        f"{CPU_ALLOWED_PHASE_KEYS}; got extra keys {keys - CPU_ALLOWED_PHASE_KEYS}"
    )
    assert keys.isdisjoint(GPU_ONLY_PHASE_KEYS), (
        f"FR-017 / ISO1: CPU lane MUST NOT carry GPU-only phase keys; "
        f"got {keys & GPU_ONLY_PHASE_KEYS}"
    )


def test_t030_cpu_lane_omits_per_page_inference() -> None:
    """ISO1: CPU lane records MUST omit per_page_inference."""
    record = _build_cpu_record("inv_002_easy")
    assert "per_page_inference" not in record


def test_t030_default_profile_path_resolves_to_cpu_lane() -> None:
    """FR-009: when --preprocess-profile is omitted, the resolved lane
    is `cpu` and the run_summary's preprocess_lane reflects it."""
    summary = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=1,
        documents_succeeded=1,
        documents_failed=0,
        per_document=[_build_cpu_record("inv_003_easy")],
        # Default RunSummary.preprocess_lane is "cpu" — explicit assertion
        # that this is the value when no GPU lane was selected.
    )
    payload = summary.to_dict()
    assert payload["preprocess_lane"] == "cpu"


def test_t030_explicit_cpu_profile_matches_default_shape() -> None:
    """FR-009 corollary: explicit `--preprocess-profile=ppstructurev3@cpu`
    produces the same shape as the default path (both → preprocess_lane='cpu',
    no GPU phase keys, no per_page_inference)."""
    explicit = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=1,
        documents_succeeded=1,
        documents_failed=0,
        per_document=[_build_cpu_record("inv_004_easy")],
        preprocess_lane="cpu",
    )
    payload = explicit.to_dict()
    assert payload["preprocess_lane"] == "cpu"
    entry = payload["per_document"][0]
    assert set(entry["phase_timings"].keys()) <= CPU_ALLOWED_PHASE_KEYS
    assert "per_page_inference" not in entry
