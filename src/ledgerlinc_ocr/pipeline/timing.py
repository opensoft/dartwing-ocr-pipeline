"""Per-stage / per-document timing capture and run-summary serializer.

Spec FR-027. Research R-009 / R-015. Data-model `StageTiming`, `RunSummary`.

Internal arithmetic stays in integer nanoseconds (``time.monotonic_ns``).
Conversion to seconds happens only at serialization time, rounded to six
decimal places (R-015). Phase keys absent from a stage's timing map mean
"not measured" (R-009 phase-key absence policy).

Feature 015 (T021): live stage adapters need access to the active
StageTiming so they can record fine-grained phase keys (e.g.,
preprocess's `rasterization` and `artifact_write` per FR-013) on
the same map the Runner is already using for the coarse `infer` /
`write` phases. The Runner sets `_CURRENT_STAGE_TIMING` (a
contextvars.ContextVar) just before invoking the stage callable;
adapters call `current_stage_timing()` to retrieve it.
"""
from __future__ import annotations

import contextvars
import json
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from ledgerlinc_ocr.pipeline.profiles import Stage
from ledgerlinc_ocr.preprocessing.identifiers import (
    AUDIT_SUB_MODULE_VOCABULARY,
    CPU_DEFAULT_DET_REC_VARIANT,
    CPU_DEFAULT_MODULE_SET,
    CPU_DEFAULT_RASTER_PROFILE,
    CPU_DEFAULT_REGION_STRATEGY,
)


# Feature 015 (T021): contextvar that the Runner populates with the
# active StageTiming for the stage currently being executed. Live
# stage adapters read this to thread fine-grained phase timings into
# the same StageTiming the Runner is using for the coarse phase. The
# default is None — meaning "no Runner is wrapping us; do not record."
_CURRENT_STAGE_TIMING: contextvars.ContextVar[Optional["StageTiming"]] = (
    contextvars.ContextVar("ledgerlinc_ocr.pipeline.timing._CURRENT_STAGE_TIMING", default=None)
)


def current_stage_timing() -> Optional["StageTiming"]:
    """Return the active per-stage StageTiming or None when not inside a
    Runner-wrapped stage call."""
    return _CURRENT_STAGE_TIMING.get()


@contextmanager
def bind_current_stage_timing(stage_timing: "StageTiming"):
    """Context manager: bind ``stage_timing`` as the active per-stage
    StageTiming for the duration of the block.

    The Runner uses this around each stage_callable invocation so live
    adapters can call ``current_stage_timing()`` to thread fine-grained
    phase keys (e.g., ``rasterization``, ``artifact_write``) into the
    same StageTiming the Runner is recording the coarse phase on.
    """
    token = _CURRENT_STAGE_TIMING.set(stage_timing)
    try:
        yield
    finally:
        _CURRENT_STAGE_TIMING.reset(token)

# Feature 014 (T027 / R-014.6): patch bump for additive `preprocess_lane`,
# `gpu_init_seconds`, `gpu_inference_seconds`, and the optional
# `gpu_lane_forced_abort` per-document flag. Consumers MUST ignore
# unknown keys; pre-feature 0.1.0 parsers continue to read 0.1.1
# output without error per the additive contract.
#
# Feature 015 (T011 / R-015.4): patch bump 0.1.1 → 0.1.2 for additive
# `phase_timings: {<name>: {seconds: float}}` and `per_page_inference:
# [{page, seconds}, …]` per-document fields. The legacy 0.1.1 flat keys
# (`stages.preprocess.{total_seconds, gpu_init_seconds,
# gpu_inference_seconds}`) are preserved unchanged for one schema
# version of back-compat (FR-014). Consumers built against 0.1.1
# continue to read 0.1.2 output without changes.
#
# Feature 016 (T003 / R-016.9 / FR-008 / /speckit.clarify Q2): codebase-level
# patch bump 0.1.2 → 0.1.3 for additive optional `phase_timings.warmup:
# {seconds: float}` per-document key. The bumped `schema_version` is emitted
# on EVERY run of the new binary regardless of whether the warmup opt-in was
# set, performed, skipped on CPU/stub, or failed; the `warmup` key itself is
# absent in the run_summary unless the warmup pass actually completed
# successfully (per feature 015 FR-016 "absent phases are omitted, not
# zeroed"). Consumers built against 0.1.2 continue to read 0.1.3 output
# without changes.
#
# Feature 017 (T004 / R-017.8 / FR-008 / FR-010 / contracts/run-summary-schema.md §1):
# codebase-level patch bump 0.1.3 → 0.1.4 for THREE additive top-level
# `run_summary` fields — `module_set_id` (string), `det_rec_variant_id`
# (string), and `ppstructure_modules_invoked` (list of strings drawn from
# the closed `AUDIT_SUB_MODULE_VOCABULARY`). All three are emitted on EVERY
# run of the new binary regardless of profile or preset selection; CPU/stub
# defaults flow from `preprocessing/identifiers.py` (`cpu-default` /
# `stub-default`). 0.1.4 is a strict superset of 0.1.3 — no existing
# field is renamed, removed, or retyped (FR-009 / FR-019). Consumers built
# against 0.1.3 continue to read 0.1.4 output without changes.
#
# Feature 018 (T004 / R-018.14 / FR-008 / FR-009 / FR-010 / FR-011 /
# contracts/run-summary-schema.md §1): codebase-level patch bump
# 0.1.4 → 0.1.5 for THREE additive top-level `run_summary` fields —
# `raster_profile_id` (string), `region_strategy_id` (string), and
# `region_strategy_fallback_count` (integer). All three are emitted on
# EVERY run of the new binary regardless of profile or preset selection;
# CPU/stub defaults flow from `preprocessing/identifiers.py`
# (`cpu-default` / `stub-default` / `0`). 0.1.5 is a strict superset of
# 0.1.4 — no existing field is renamed, removed, or retyped (FR-010 /
# FR-022). Consumers built against 0.1.4 continue to read 0.1.5 output
# without changes.
SCHEMA_VERSION = "0.1.5"


def _ns_to_seconds(ns: int) -> float:
    return round(ns / 1e9, 6)


@dataclass
class StageTiming:
    """Captured timings for a single stage on a single document."""
    stage: Stage
    phases_ns: dict[str, int] = field(default_factory=dict)
    total_ns: int = 0

    def add_phase(self, phase_key: str, ns: int) -> None:
        self.phases_ns[phase_key] = self.phases_ns.get(phase_key, 0) + ns

    def to_seconds_map(self) -> dict[str, float]:
        """Serialize to {<phase>_seconds, total_seconds} with six-decimal rounding."""
        out: dict[str, float] = {
            f"{key}_seconds": _ns_to_seconds(value)
            for key, value in self.phases_ns.items()
        }
        out["total_seconds"] = _ns_to_seconds(self.total_ns)
        return out


@contextmanager
def measure_total(timing: StageTiming) -> Iterator[None]:
    """Context manager that records the entry-to-exit duration into ``total_ns``.

    Always sets ``total_ns`` even if the wrapped block raises -- the
    failure path is timed too (R-009 phase-key absence policy).
    """
    start = time.monotonic_ns()
    try:
        yield
    finally:
        timing.total_ns += time.monotonic_ns() - start


@contextmanager
def measure_phase(timing: StageTiming, phase_key: str) -> Iterator[None]:
    """Context manager that adds the wrapped block's duration to ``phases_ns[phase_key]``."""
    start = time.monotonic_ns()
    try:
        yield
    finally:
        timing.add_phase(phase_key, time.monotonic_ns() - start)


@dataclass
class DocumentTimings:
    """All stage timings captured for a single document."""
    stages: dict[Stage, StageTiming] = field(default_factory=dict)

    def get_or_create(self, stage: Stage) -> StageTiming:
        if stage not in self.stages:
            self.stages[stage] = StageTiming(stage=stage)
        return self.stages[stage]

    def to_summary_dict(self) -> dict[str, dict[str, float]]:
        return {
            stage: timing.to_seconds_map()
            for stage, timing in self.stages.items()
        }


@dataclass
class RunSummary:
    """End-of-run JSON-Lines run summary for warm-corpus mode (R-009).

    Feature 014 (T027) adds the additive top-level field
    ``preprocess_lane`` (always present after this feature; values
    "cpu" or "gpu<N>"). Per-document timing maps may also carry the
    additive `gpu_init_seconds` and `gpu_inference_seconds` phase
    keys per R-009's phase-key-absence policy (T028 / T029 / T030).

    Feature 017 (T006 / R-017.5 / R-017.7 / R-017.8 /
    contracts/run-summary-schema.md §2–§3) adds three additive
    top-level fields: ``module_set_id``, ``det_rec_variant_id``, and
    ``ppstructure_modules_invoked``. All three are emitted on every
    run regardless of profile (FR-008 / FR-010); their default values
    reflect the CPU lane defaults from
    ``preprocessing/identifiers.py``. Stub-adapter runs override
    these via ``stub-default`` strings; GPU-lane runs override via
    the resolved preset names from
    ``preprocessing/presets.py::resolve_module_set`` /
    ``resolve_det_rec_variant`` (US1/US2 wiring lands those values).

    Feature 018 (T006 / R-018.8 / R-018.14 /
    contracts/run-summary-schema.md §2–§3) adds three additive
    top-level fields: ``raster_profile_id``, ``region_strategy_id``,
    and ``region_strategy_fallback_count``. All three are emitted on
    every run regardless of profile (FR-008 / FR-009 / FR-011);
    their default values reflect the CPU lane defaults from
    ``preprocessing/identifiers.py`` (CPU_DEFAULT_RASTER_PROFILE /
    CPU_DEFAULT_REGION_STRATEGY / 0). Stub-adapter runs override via
    ``stub-default`` strings; GPU-lane runs override via the resolved
    preset names from
    ``preprocessing/raster_profiles.py::resolve_raster_profile``
    (US1) / ``preprocessing/region_strategies.py::resolve_region_strategy``
    (US2). The ``region_strategy_fallback_count`` accumulator is
    incremented per fallen-back document by the orchestrator in
    ``preprocessing/pipeline.py`` (US2 wiring) per R-018.7 / R-018.8.
    """
    stack_preset: str | None
    resolved_profiles: dict[Stage, str]
    execution_slice: dict[str, str]
    on_failure: str
    documents_total: int
    documents_succeeded: int
    documents_failed: int
    profile_initialization_seconds: dict[Stage, float] = field(default_factory=dict)
    per_document: list[dict[str, Any]] = field(default_factory=list)
    preprocess_lane: str = "cpu"  # T027: additive (default for backward compat)
    # Feature 017 (T006): three additive top-level fields. Defaults reflect
    # the CPU lane / no-preset case so existing call sites compile without
    # change; US1/US2 wiring overrides on GPU/stub lanes.
    module_set_id: str = CPU_DEFAULT_MODULE_SET
    det_rec_variant_id: str = CPU_DEFAULT_DET_REC_VARIANT
    ppstructure_modules_invoked: list[str] = field(default_factory=list)
    # Feature 018 (T006 / R-018.14): three additive top-level fields.
    # Defaults reflect the CPU lane / no-preset case; US1/US2 wiring
    # overrides on GPU/stub lanes per contracts/cli-contract.md §1.
    raster_profile_id: str = CPU_DEFAULT_RASTER_PROFILE
    region_strategy_id: str = CPU_DEFAULT_REGION_STRATEGY
    region_strategy_fallback_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        # Last-line-of-defense canonicalization for the closed-vocabulary
        # contract on `ppstructure_modules_invoked` (R-017.7). The audit
        # callable in `presets.py` already filters to vocabulary on
        # construction; this serializer enforces the same invariant on
        # emit so a buggy caller cannot leak arbitrary strings onto the
        # wire format.
        _canonical_audit_modules = sorted(
            {str(m) for m in self.ppstructure_modules_invoked}
            & set(AUDIT_SUB_MODULE_VOCABULARY)
        )
        return {
            "kind": "run_summary",
            "schema_version": SCHEMA_VERSION,
            "stack_preset": self.stack_preset,
            "resolved_profiles": dict(self.resolved_profiles),
            "execution_slice": dict(self.execution_slice),
            "on_failure": self.on_failure,
            "documents_total": self.documents_total,
            "documents_succeeded": self.documents_succeeded,
            "documents_failed": self.documents_failed,
            "profile_initialization_seconds": dict(
                self.profile_initialization_seconds
            ),
            "per_document": list(self.per_document),
            "preprocess_lane": self.preprocess_lane,  # T027 additive
            # Feature 017 additive top-level fields (T006 /
            # contracts/run-summary-schema.md §3): emitted in fixed
            # order between `preprocess_lane` and the closing brace.
            "module_set_id": self.module_set_id,
            "det_rec_variant_id": self.det_rec_variant_id,
            "ppstructure_modules_invoked": _canonical_audit_modules,
            # Feature 018 additive top-level fields (T006 /
            # contracts/run-summary-schema.md §2): emitted AFTER
            # feature 017's three fields and before the closing brace
            # in fixed order. Always-emit per FR-008 / FR-009 / FR-011.
            "raster_profile_id": self.raster_profile_id,
            "region_strategy_id": self.region_strategy_id,
            "region_strategy_fallback_count": self.region_strategy_fallback_count,
        }

    def as_json_line(self) -> str:
        return json.dumps(
            self.to_dict(),
            separators=(",", ":"),
            ensure_ascii=False,
        )


def emit_run_summary(summary: RunSummary, *, stream: Any = None) -> None:
    """Emit the run summary as the last stdout line (R-009)."""
    target = stream if stream is not None else sys.stdout
    target.write(summary.as_json_line() + "\n")


def attach_one_time_gpu_phases(
    record: dict[str, Any],
    readout: Any,
    *,
    warmup_seconds: float | None = None,
) -> None:
    """Attach the GPU one-time phase keys (`paddle_import`,
    `gpu_bind_probe`, `engine_init`, and — feature 016 — `warmup`) to a
    per-document run_summary record's `phase_timings` block (feature 015 /
    T027 / R-015.4; feature 016 / T004 / R-016.8).

    `readout` is a `PreflightReadout` (or any object with an `evidence`
    attribute carrying the three `*_seconds` fields). Phases whose source
    value is None are omitted (FR-016). The record's `phase_timings`
    sub-dict is created if absent.

    Feature 016 (T004): the keyword-only ``warmup_seconds`` parameter is
    additive; when non-``None``, ``record["phase_timings"]["warmup"]`` is
    set to ``{"seconds": round(warmup_seconds, 6)}`` (six-decimal rounding
    per `contracts/run-summary-schema.md` §2). When ``None`` (default —
    warmup not run, or warmup failed before completing), the ``warmup``
    key is omitted (preserving feature 015 FR-016 "absent phases are
    omitted, not zeroed"). The four first-doc one-time GPU phases form a
    coherent set per `contracts/module-invariants.md` I-11."""
    ev = getattr(readout, "evidence", None)
    if ev is None:
        # Even with no readout, warmup_seconds may have been captured;
        # still attach it so callers can wire warmup independently of
        # preflight evidence availability.
        if warmup_seconds is not None:
            phase_timings = record.setdefault("phase_timings", {})
            phase_timings["warmup"] = {"seconds": round(warmup_seconds, 6)}
        return
    phase_timings = record.setdefault("phase_timings", {})
    paddle_import_seconds = getattr(ev, "paddle_import_seconds", None)
    gpu_bind_probe_seconds = getattr(ev, "gpu_bind_probe_seconds", None)
    engine_init_seconds = getattr(ev, "ppstructurev3_init_seconds", None)
    if paddle_import_seconds is not None:
        phase_timings["paddle_import"] = {"seconds": paddle_import_seconds}
    if gpu_bind_probe_seconds is not None:
        phase_timings["gpu_bind_probe"] = {"seconds": gpu_bind_probe_seconds}
    if engine_init_seconds is not None:
        phase_timings["engine_init"] = {"seconds": engine_init_seconds}
    if warmup_seconds is not None:
        phase_timings["warmup"] = {"seconds": round(warmup_seconds, 6)}


def build_per_document_success(
    *,
    document_id: str,
    folder: str,
    timings: DocumentTimings,
    phase_timings: dict[str, dict[str, float]] | None = None,
    per_page_inference: list[dict[str, Any]] | list[tuple[int, float]] | None = None,
) -> dict[str, Any]:
    """Build a successful per-document run_summary entry.

    Feature 015 (T012 / R-015.4): adds two optional keyword-only
    parameters carrying the new structured run_summary 0.1.2 shape:

    - ``phase_timings``: ``{<phase_name>: {"seconds": <float>}}`` — when
      provided non-None, attached to the returned dict under
      ``"phase_timings"``. Phases that did not run MUST be passed as
      omitted dict keys (callers' responsibility per FR-016).
    - ``per_page_inference``: list of ``{"page": int, "seconds": float}``
      records OR list of ``(page, seconds)`` tuples (auto-converted) —
      when provided non-None, attached under ``"per_page_inference"``.

    The legacy ``stages`` flat-key emission is preserved unchanged for
    back-compat (one schema version of 0.1.1 → 0.1.2 transition)."""
    out: dict[str, Any] = {
        "document_id": document_id,
        "folder": folder,
        "status": "success",
        "stages": timings.to_summary_dict(),
    }
    if phase_timings is not None:
        out["phase_timings"] = dict(phase_timings)
    if per_page_inference is not None:
        out["per_page_inference"] = _normalize_per_page(per_page_inference)
    return out


def _normalize_per_page(
    per_page: list[dict[str, Any]] | list[tuple[int, float]],
) -> list[dict[str, Any]]:
    """Accept either dict-form or tuple-form per-page records and return
    the canonical dict-form list."""
    out: list[dict[str, Any]] = []
    for entry in per_page:
        if isinstance(entry, tuple) and len(entry) == 2:
            page, seconds = entry
            out.append({"page": int(page), "seconds": float(seconds)})
        elif isinstance(entry, dict) and "page" in entry and "seconds" in entry:
            out.append({"page": int(entry["page"]), "seconds": float(entry["seconds"])})
        else:
            raise ValueError(
                f"per_page_inference entry has unsupported shape: {entry!r}"
            )
    return out


def build_per_document_failure(
    *,
    document_id: str,
    folder: str,
    failed_stage: str,
    exit_code: int,
    message: str,
    timings: DocumentTimings | None = None,
    gpu_lane_forced_abort: bool = False,
    phase_timings: dict[str, dict[str, float]] | None = None,
    per_page_inference: list[dict[str, Any]] | list[tuple[int, float]] | None = None,
) -> dict[str, Any]:
    """Feature 014 (T024 / CF9): adds the optional keyword-only
    ``gpu_lane_forced_abort: bool = False`` parameter. When ``True``,
    the returned dict carries the key ``"gpu_lane_forced_abort": True``
    (always ``true`` when present per data-model §RunSummary). When
    ``False`` (default; every existing failure path), the key is
    absent. The signature extension is purely additive — existing
    callers without the kwarg continue to behave as before."""
    out: dict[str, Any] = {
        "document_id": document_id,
        "folder": folder,
        "status": "failure",
        "failed_stage": failed_stage,
        "exit_code": exit_code,
        "message": message,
    }
    if timings is not None and timings.stages:
        out["stages"] = timings.to_summary_dict()
    if gpu_lane_forced_abort:
        out["gpu_lane_forced_abort"] = True
    # Feature 015 (T012 / R-015.5 / FP1): partial phase_timings and
    # per_page_inference may be attached to a failed-doc record. Phases
    # that did not run MUST be passed as omitted dict keys (FR-016).
    if phase_timings is not None:
        out["phase_timings"] = dict(phase_timings)
    if per_page_inference is not None:
        out["per_page_inference"] = _normalize_per_page(per_page_inference)
    return out


__all__ = [
    "DocumentTimings",
    "RunSummary",
    "SCHEMA_VERSION",
    "StageTiming",
    "build_per_document_failure",
    "build_per_document_success",
    "emit_run_summary",
    "measure_phase",
    "measure_total",
]
