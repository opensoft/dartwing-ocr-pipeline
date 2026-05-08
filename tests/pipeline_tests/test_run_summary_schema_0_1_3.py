"""Run-summary schema 0.1.3 patch-bump tests (feature 016 / T013 / FR-008 / R-016.9).

Sibling of `test_run_summary_schema_0_1_2.py` (feature 015). Adds the
0.1.3-specific regression checks: codebase-level `SCHEMA_VERSION = "0.1.3"`,
the additive optional `phase_timings.warmup` shape, and the joint-presence
rule (I-11) for the four first-doc one-time GPU phases.

CPU-safe: no paddle / MIOpen / GPU. Exercises `attach_one_time_gpu_phases`
directly and inspects the resulting record dict, without invoking any
preprocessing stages."""
from __future__ import annotations

import json

import pytest

from ledgerlinc_ocr.pipeline import timing
from ledgerlinc_ocr.pipeline.timing import (
    DocumentTimings,
    RunSummary,
    SCHEMA_VERSION,
    attach_one_time_gpu_phases,
    build_per_document_failure,
    build_per_document_success,
)


# ---------------------------------------------------------------------------
# I-9 / FR-008 / R-016.9: codebase-level SCHEMA_VERSION bump 0.1.2 → 0.1.3
# ---------------------------------------------------------------------------


def test_schema_version_is_0_1_3_codebase_level() -> None:
    """`SCHEMA_VERSION` is exactly `"0.1.3"` for every run of the new
    binary regardless of warmup state (per /speckit.clarify Q2 +
    `contracts/run-summary-schema.md` §1)."""
    assert timing.SCHEMA_VERSION == "0.1.3", (
        f"feature 016 must bump SCHEMA_VERSION from 0.1.2 to 0.1.3 "
        f"(got {timing.SCHEMA_VERSION!r})"
    )
    assert SCHEMA_VERSION == "0.1.3"


def test_run_summary_emits_0_1_3_in_json_line() -> None:
    """A serialized `run_summary` line carries `schema_version: "0.1.3"`
    on the wire."""
    summary = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
    line = summary.as_json_line()
    parsed = json.loads(line)
    assert parsed["schema_version"] == "0.1.3"


# ---------------------------------------------------------------------------
# Additive `phase_timings.warmup` shape (FR-006 / contracts/run-summary-schema.md §2)
# ---------------------------------------------------------------------------


def test_warmup_absent_when_attach_not_called() -> None:
    """Without invoking `attach_one_time_gpu_phases`, the per-doc record
    has no `phase_timings.warmup` key (FR-002 / SC-002)."""
    record = build_per_document_success(
        document_id="inv_001_easy",
        folder="tests/stage1_vendor_identity/inv_001_easy",
        timings=DocumentTimings(),
    )
    assert "warmup" not in record.get("phase_timings", {})


def test_warmup_absent_when_attach_called_without_warmup_seconds() -> None:
    """Calling `attach_one_time_gpu_phases(record, readout)` WITHOUT the
    `warmup_seconds` kwarg leaves `phase_timings.warmup` absent (FR-016
    "absent phases are omitted, not zeroed")."""
    record = {"phase_timings": {}}
    attach_one_time_gpu_phases(record, None)
    assert "warmup" not in record["phase_timings"]


def test_warmup_present_with_correct_shape_when_seconds_provided() -> None:
    """Calling `attach_one_time_gpu_phases(record, readout, warmup_seconds=
    0.123456789)` attaches `phase_timings.warmup = {"seconds": 0.123457}`
    (six-decimal rounding per `contracts/run-summary-schema.md` §2)."""
    record = {"phase_timings": {}}
    attach_one_time_gpu_phases(record, None, warmup_seconds=0.123456789)
    warmup_entry = record["phase_timings"].get("warmup")
    assert warmup_entry is not None
    assert set(warmup_entry.keys()) == {"seconds"}, (
        f"phase_timings.warmup MUST have exactly one key 'seconds'; "
        f"got {warmup_entry!r}"
    )
    assert warmup_entry["seconds"] == pytest.approx(0.123457), (
        f"warmup.seconds must be six-decimal-rounded; got {warmup_entry['seconds']!r}"
    )


def test_warmup_seconds_zero_is_attached_as_zero() -> None:
    """Edge case: `warmup_seconds=0.0` (which would not occur in practice
    — `run_warmup` raises ClockAnomaly for non-positive seconds) is still
    a valid float and the helper attaches it. The tests exists to lock
    the rounding/serialization for any unusual float value."""
    record = {"phase_timings": {}}
    attach_one_time_gpu_phases(record, None, warmup_seconds=0.0)
    assert record["phase_timings"]["warmup"] == {"seconds": 0.0}


# ---------------------------------------------------------------------------
# I-11: joint-presence rule for first-doc one-time GPU phases
# ---------------------------------------------------------------------------


class _StubEvidence:
    """Minimal fake of preflight `evidence` carrying just the three
    *_seconds fields the helper reads."""

    def __init__(
        self,
        paddle_import_seconds: float | None,
        gpu_bind_probe_seconds: float | None,
        ppstructurev3_init_seconds: float | None,
    ) -> None:
        self.paddle_import_seconds = paddle_import_seconds
        self.gpu_bind_probe_seconds = gpu_bind_probe_seconds
        self.ppstructurev3_init_seconds = ppstructurev3_init_seconds


class _StubReadout:
    def __init__(self, evidence: _StubEvidence) -> None:
        self.evidence = evidence


def test_warmup_attaches_alongside_one_time_phases() -> None:
    """When `attach_one_time_gpu_phases` is invoked with both a non-None
    readout and `warmup_seconds`, the four first-doc one-time GPU phase
    keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`)
    appear together on the same `phase_timings` block per
    `contracts/module-invariants.md` I-11."""
    record = {"phase_timings": {}}
    readout = _StubReadout(
        _StubEvidence(
            paddle_import_seconds=0.04,
            gpu_bind_probe_seconds=0.02,
            ppstructurev3_init_seconds=1.5,
        )
    )
    attach_one_time_gpu_phases(record, readout, warmup_seconds=0.789)
    pt = record["phase_timings"]
    assert pt["paddle_import"] == {"seconds": 0.04}
    assert pt["gpu_bind_probe"] == {"seconds": 0.02}
    assert pt["engine_init"] == {"seconds": 1.5}
    assert pt["warmup"] == {"seconds": 0.789}


def test_warmup_attaches_even_when_readout_evidence_is_none() -> None:
    """Defensive case: if the readout has no evidence object (rare, but
    possible if `_PREFLIGHT_READOUT` was somehow detached), the helper
    still attaches `phase_timings.warmup` when `warmup_seconds` is
    provided. This protects the warmup-success-but-readout-missing
    edge case."""
    record = {"phase_timings": {}}
    attach_one_time_gpu_phases(record, None, warmup_seconds=0.5)
    assert record["phase_timings"] == {"warmup": {"seconds": 0.5}}


def test_warmup_seconds_present_no_engine_init_present_when_readout_partial() -> None:
    """If the readout has only `ppstructurev3_init_seconds=None` (engine
    init not measured), `engine_init` is absent but `warmup` still
    attaches when `warmup_seconds` is provided. The four-key set is
    coherent at the helper level — individual keys may still be absent
    when their underlying source value is None per FR-016."""
    record = {"phase_timings": {}}
    readout = _StubReadout(
        _StubEvidence(
            paddle_import_seconds=0.04,
            gpu_bind_probe_seconds=0.02,
            ppstructurev3_init_seconds=None,
        )
    )
    attach_one_time_gpu_phases(record, readout, warmup_seconds=0.5)
    pt = record["phase_timings"]
    assert "paddle_import" in pt
    assert "gpu_bind_probe" in pt
    assert "engine_init" not in pt  # source value was None
    assert pt["warmup"] == {"seconds": 0.5}


# ---------------------------------------------------------------------------
# Backwards-compat: 0.1.2 fields are unchanged in 0.1.3 (FR-008 lineage)
# ---------------------------------------------------------------------------


def test_legacy_flat_keys_still_emitted_in_0_1_3() -> None:
    """The legacy 0.1.1 flat key `total_seconds` continues to appear in
    `stages.preprocess` for back-compat (FR-008 / FR-009 lineage)."""
    timings = DocumentTimings()
    pt = timings.get_or_create("preprocess")
    pt.total_ns = 1_500_000_000  # 1.5 seconds in ns
    record = build_per_document_success(
        document_id="inv_002_easy",
        folder="tests/stage1_vendor_identity/inv_002_easy",
        timings=timings,
    )
    stages = record["stages"]
    preprocess_stage = stages["preprocess"]
    assert "total_seconds" in preprocess_stage, (
        "0.1.3 must continue to emit legacy stages.preprocess.total_seconds for back-compat"
    )
    assert preprocess_stage["total_seconds"] == pytest.approx(1.5)
