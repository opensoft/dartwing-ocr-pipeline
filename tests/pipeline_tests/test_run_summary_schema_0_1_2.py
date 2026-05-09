"""Run-summary schema 0.1.2 patch-bump tests (feature 015 / T004 / T025).

Covers PT5, CH2, CH3 from `contracts/module-invariants.md` plus the
US3 cross-cutting consistency case added in T025.
"""
from __future__ import annotations

import json
from typing import Any

import pytest


timing = pytest.importorskip("ledgerlinc_ocr.pipeline.timing")


# Expected FR-013 phase keys (single source of truth = spec.md §FR-013).
ALL_PHASE_KEYS = {
    "paddle_import",
    "gpu_bind_probe",
    "engine_init",
    "warmup",
    "rasterization",
    "artifact_write",
    "total",
}
GPU_FIRST_DOC_PHASES = {"paddle_import", "gpu_bind_probe", "engine_init"}
PER_DOC_PHASES = {"rasterization", "artifact_write", "total"}


# ---------------------------------------------------------------------------
# PT5 — schema_version is at least 0.1.2 (current chain head: 0.1.4 after feature 017)
# ---------------------------------------------------------------------------

def test_pt5_schema_version_is_current_chain_head() -> None:
    """The binding contract this test enforces is "SCHEMA_VERSION ≥ 0.1.2"
    — set in feature 015 and preserved by every later bump. The
    producer's current chain head is ``0.1.4`` (feature 017 / T004 /
    R-017.8 added three additive top-level identifier fields:
    ``module_set_id``, ``det_rec_variant_id``,
    ``ppstructure_modules_invoked``). Feature 016 added
    ``test_run_summary_schema_0_1_3.py``; feature 017 will add
    ``test_run_summary_schema_0_1_4.py`` (US1 T014). This test stays
    pinned to the chain head so a regression to a stale value is
    caught here too."""
    # Tuple comparison instead of lexical string comparison — string
    # `>=` works for "0.1.4" but breaks at "0.1.10" lexically (review
    # MEDIUM finding). Tuple of ints is monotonic.
    _version_tuple = tuple(int(p) for p in timing.SCHEMA_VERSION.split("."))
    assert _version_tuple >= (0, 1, 2), (
        f"SCHEMA_VERSION must be at least 0.1.2 (feature 015 floor); "
        f"got {timing.SCHEMA_VERSION!r}. Current chain head is 0.1.4 "
        f"(feature 017). Historical 0.1.1 → 0.1.2 (feature 015) and "
        f"0.1.2 → 0.1.3 (feature 016) bumps still implied by the chain."
    )


# ---------------------------------------------------------------------------
# CH2 — no new stdout `kind` introduced
# ---------------------------------------------------------------------------
# The set of allowed JSONL `kind` values across all stdout-emitting code
# paths in the pipeline. Feature 015 MUST NOT add a new value.

ALLOWED_STDOUT_KINDS = {
    "run_summary",          # pipeline/timing.py emit_run_summary
    "preflight_readout",    # preprocessing/preflight_cli.py
    "failure",              # pipeline/cli.py _emit_failure
    "artifact_set",         # pipeline/cli.py _emit_stdout_summary (per-doc artifacts)
}


def test_ch2_run_summary_kind_is_canonical_value() -> None:
    """RunSummary serializes with the exact 'run_summary' kind, no variants."""
    summary = timing.RunSummary(
        stack_preset=None,
        resolved_profiles={},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
    line = summary.as_json_line()
    parsed = json.loads(line)
    assert parsed["kind"] == "run_summary"
    assert parsed["kind"] in ALLOWED_STDOUT_KINDS


# ---------------------------------------------------------------------------
# CH3 — warmup phase absent by default
# ---------------------------------------------------------------------------

def test_ch3_warmup_phase_absent_by_default() -> None:
    """Feature 015 does not introduce a synthetic warmup pass; the
    `warmup` key must be absent from `phase_timings` unless some other
    code path actually performs warmup (Q2 / FR-013 / FR-016)."""
    # Build a per-doc record with the full GPU-first-doc phase set as
    # feature 015 would emit it. `warmup` is intentionally not in the dict.
    phase_timings = {
        "paddle_import": {"seconds": 1.42},
        "gpu_bind_probe": {"seconds": 0.04},
        "engine_init": {"seconds": 41.21},
        "rasterization": {"seconds": 1.13},
        "artifact_write": {"seconds": 0.05},
        "total": {"seconds": 43.85},
    }
    record = timing.build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=timing.DocumentTimings(),
        phase_timings=phase_timings,
    )
    assert "warmup" not in record["phase_timings"], (
        "CH3: warmup MUST NOT appear in default feature-015 emission "
        "(reserved phase only per spec FR-013 + Q2)"
    )


# ---------------------------------------------------------------------------
# T025 — US3 consistency check: emitted set vs. FR-013 vocabulary
# ---------------------------------------------------------------------------

def test_t025_first_doc_gpu_phase_keys_subset_and_superset_rules() -> None:
    """First-doc GPU run: `phase_timings` keys form a SUPERSET of the
    required steady-state phases plus the GPU one-time phases, and a
    SUBSET of the FR-013 vocabulary (warmup absent per Q2)."""
    phase_timings = {
        "paddle_import": {"seconds": 1.42},
        "gpu_bind_probe": {"seconds": 0.04},
        "engine_init": {"seconds": 41.21},
        "rasterization": {"seconds": 1.13},
        "artifact_write": {"seconds": 0.05},
        "total": {"seconds": 43.85},
    }
    record = timing.build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=timing.DocumentTimings(),
        phase_timings=phase_timings,
    )
    keys = set(record["phase_timings"].keys())
    assert keys <= ALL_PHASE_KEYS, f"keys must be subset of FR-013 vocab; got {keys - ALL_PHASE_KEYS} extra"
    required_first_doc = GPU_FIRST_DOC_PHASES | PER_DOC_PHASES
    assert required_first_doc <= keys, (
        f"first-doc GPU run must include all of {required_first_doc}; missing {required_first_doc - keys}"
    )


def test_t025_subsequent_doc_omits_one_time_gpu_keys() -> None:
    """Subsequent-doc on warm corpus: `phase_timings` MUST NOT contain the
    GPU one-time phases; only `rasterization`, `artifact_write`, `total`."""
    phase_timings = {
        "rasterization": {"seconds": 1.10},
        "artifact_write": {"seconds": 0.05},
        "total": {"seconds": 9.50},
    }
    record = timing.build_per_document_success(
        document_id="inv_002_easy",
        folder="tests/stage1_vendor_identity/inv_002_easy",
        timings=timing.DocumentTimings(),
        phase_timings=phase_timings,
    )
    keys = set(record["phase_timings"].keys())
    assert keys == PER_DOC_PHASES, (
        f"subsequent-doc must contain exactly {PER_DOC_PHASES}; got {keys}"
    )
    assert keys.isdisjoint(GPU_FIRST_DOC_PHASES), (
        "subsequent-doc MUST NOT contain GPU one-time keys"
    )


def test_t025_per_page_inference_pages_strictly_ascending_one_based() -> None:
    record = timing.build_per_document_success(
        document_id="inv_003_medium",
        folder="tests/stage1_vendor_identity/inv_003_medium",
        timings=timing.DocumentTimings(),
        phase_timings={"total": {"seconds": 18.0}, "rasterization": {"seconds": 1.5}, "artifact_write": {"seconds": 0.1}},
        per_page_inference=[{"page": 1, "seconds": 5.0}, {"page": 2, "seconds": 4.8}, {"page": 3, "seconds": 6.5}],
    )
    pages = [p["page"] for p in record["per_page_inference"]]
    assert pages[0] == 1, "PT3: pages 1-based"
    assert pages == sorted(pages), "PT3: pages strictly ascending"
