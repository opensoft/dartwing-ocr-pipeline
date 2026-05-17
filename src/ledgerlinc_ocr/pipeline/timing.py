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
import math
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
    CPU_DEFAULT_PREPROCESS_STRATEGY,
    CPU_DEFAULT_RASTER_PROFILE,
    CPU_DEFAULT_REGION_STRATEGY,
    EVIDENCE_GATE_ID_DEFAULT,
)


def _default_evidence_gate_state_counts() -> dict[str, int]:
    """Default value for ``RunSummary.evidence_gate_state_counts``.

    The closed three-state vocabulary is fixed at landing — all three keys
    are always present (NOT sparse) per R-020.10 / MI-17 / contracts/
    run-summary-schema.md §2. Returned as a fresh dict per call (dataclass
    ``default_factory`` semantics) so two RunSummary instances do not share
    a mutable default.
    """
    return {"sufficient": 0, "borderline": 0, "insufficient": 0}


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
#
# Feature 019 (T004 / R-019.14 / FR-007 / FR-008 / FR-010 /
# contracts/run-summary-schema.md §1): codebase-level patch bump
# 0.1.5 → 0.1.6 for TWO additive top-level `run_summary` fields —
# `preprocess_strategy_id` (string) and `ocr_only_fallback_count`
# (integer). Both are emitted on EVERY run of the new binary regardless
# of profile or preset selection; CPU/stub defaults flow from
# `preprocessing/identifiers.py` (`cpu-default` / `stub-default` / `0`).
# 0.1.6 is a strict superset of 0.1.5 — no existing field is renamed,
# removed, or retyped (FR-009 / FR-022). Consumers built against 0.1.5
# continue to read 0.1.6 output without changes.
#
# Feature 020 (T025 / R-020.9 / FR-008 / FR-010 /
# contracts/run-summary-schema.md): codebase-level patch bump
# 0.1.6 → 0.1.7 for FOUR additive top-level `run_summary` fields —
# `evidence_gate_id` (string, always `"v1"` at landing per R-020.2),
# `evidence_gate_state_counts` (object with all three keys
# `sufficient`/`borderline`/`insufficient`, default-zero integers),
# `evidence_gate_documents` (array of per-doc records with `document_id`,
# `decision`, and the five FR-001 signal values), and
# `evidence_gate_suppressed_fallback_count` (integer, default 0;
# increments only when shape (b) suppression actually fires).
# All four are emitted on EVERY run of the new binary regardless of
# profile or preset selection per FR-008 / FR-010 / MI-16 / MI-17.
# Unlike features 017/018/019, the `evidence_gate_id` axis emits the
# same `"v1"` identifier uniformly on CPU, stub-adapter, and GPU lanes
# — the gate is a pure read over `preprocess_output.json` content and
# runs on every profile (FR-014 / data-model.md §9). 0.1.7 is a strict
# superset of 0.1.6 — no existing field is renamed, removed, or
# retyped (FR-011 / FR-022 / MI-19). Consumers built against 0.1.6
# continue to read 0.1.7 output without changes.
SCHEMA_VERSION = "0.1.7"


def _ns_to_seconds(ns: int) -> float:
    return round(ns / 1e9, 6)


# Feature 020 (Phase 3 post-review): closed-vocabulary key sets for the
# evidence-gate per-document record. Used by `_canonicalize_evidence_gate_record`
# at the serializer boundary so a buggy caller cannot leak extra keys
# (or raw token fields) onto the operator-facing run_summary line. This
# is the last-line-of-defense PII closure parallel to the
# `ppstructure_modules_invoked` sort-and-intersect canonicalization
# already enforced for that field.
_EVIDENCE_GATE_RECORD_KEYS: frozenset[str] = frozenset(
    {"document_id", "decision", "signals"}
)
_EVIDENCE_GATE_SIGNAL_KEYS: frozenset[str] = frozenset(
    {
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }
)
_EVIDENCE_GATE_DECISION_VOCAB: frozenset[str] = frozenset(
    {"sufficient", "borderline", "insufficient"}
)


def _safe_int(value: Any, default: int = 0) -> int:
    """Coerce ``value`` to a non-negative int; return ``default`` on
    anything else (None, bool, non-numeric, infinity, NaN, negative).

    Phase 4 hardening (post-review): the prior ``int(...)`` call raised
    on bad input (e.g., ``int("not a number")``); also `bool` is a
    subclass of `int` so ``int(True) == 1`` silently. This helper is
    used at the serializer boundary where a buggy caller's bad scalar
    must NOT propagate to the wire format.
    """
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value if value >= 0 else default
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return coerced if coerced >= 0 else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to a finite float in ``[0.0, 1.0]``; return
    ``default`` on anything else (None, non-numeric, NaN, infinity,
    out-of-range).

    Phase 4 hardening (post-review): the prior ``float(...)`` call
    accepted ``float("nan")`` / ``float("inf")`` (which emit non-finite
    JSON) and raised on non-numeric strings. This helper clamps to the
    contracted ``[0.0, 1.0]`` range and replaces NaN/Inf with the
    safe default at the serializer boundary.
    """
    if isinstance(value, bool) or value is None:
        return default
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(coerced) or math.isinf(coerced):
        return default
    return max(0.0, min(1.0, coerced))


def _canonicalize_evidence_gate_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """Restrict a per-document gate record to the documented shape.

    Returns a fresh dict with EXACTLY the three top-level keys
    (``document_id``, ``decision``, ``signals``) and the nested
    ``signals`` dict restricted to the five FR-001 signal names. Extra
    keys at either level are dropped; out-of-range / non-finite /
    wrong-typed values are coerced to safe defaults via
    ``_safe_int`` / ``_safe_float``; decision strings outside the
    closed vocabulary are clamped to ``"insufficient"``.

    Defense-in-depth for FR-003 PII closure: the
    ``build_evidence_gate_document_record`` constructor already produces
    the canonical shape, but a future code path that builds records
    directly (or a regression that lets caller-supplied extras
    through) cannot leak raw token strings, matched tax-ID values, or
    other invoice content onto the run_summary wire format.
    """
    document_id = str(record.get("document_id", ""))
    decision = record.get("decision", "insufficient")
    if decision not in _EVIDENCE_GATE_DECISION_VOCAB:
        decision = "insufficient"
    raw_signals = record.get("signals") or {}
    if not isinstance(raw_signals, dict):
        raw_signals = {}
    return {
        "document_id": document_id,
        "decision": decision,
        "signals": {
            "vendor_name_candidate_count": _safe_int(
                raw_signals.get("vendor_name_candidate_count")
            ),
            "header_band_token_density": _safe_int(
                raw_signals.get("header_band_token_density")
            ),
            "ocr_detection_confidence_mean": _safe_float(
                raw_signals.get("ocr_detection_confidence_mean")
            ),
            "business_suffix_present": bool(
                raw_signals.get("business_suffix_present", False)
            ),
            "tax_id_shaped_present": bool(
                raw_signals.get("tax_id_shaped_present", False)
            ),
        },
    }


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

    Feature 019 (T006 / R-019.14 /
    contracts/run-summary-schema.md §2–§3) adds two additive
    top-level fields: ``preprocess_strategy_id`` (string) and
    ``ocr_only_fallback_count`` (integer). Both are emitted on every
    run regardless of profile (FR-007 / FR-008 / FR-010); their
    default values reflect the CPU lane defaults from
    ``preprocessing/identifiers.py`` (CPU_DEFAULT_PREPROCESS_STRATEGY
    / 0). Stub-adapter runs override via ``stub-default`` strings;
    GPU-lane runs override via the resolved preset name from
    ``preprocessing/preprocess_strategies.py::resolve_preprocess_strategy``
    (US1 wiring). The ``ocr_only_fallback_count`` accumulator is
    incremented per fallen-back document by the orchestrator in
    ``preprocessing/pipeline.py`` (US3 wiring) per R-019.10 / I-019.4.
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
    # Feature 019 (T006 / R-019.14): two additive top-level fields.
    # Defaults reflect the CPU lane / no-preset case; US1 wiring
    # overrides on GPU runs (resolved preset name from
    # `preprocess_strategies.py::resolve_preprocess_strategy`); stub
    # adapter overrides to `stub-default`. US3 wiring increments
    # `ocr_only_fallback_count` per fallen-back document via the
    # orchestrator in `preprocessing/pipeline.py` per R-019.10 / I-019.4.
    preprocess_strategy_id: str = CPU_DEFAULT_PREPROCESS_STRATEGY
    ocr_only_fallback_count: int = 0
    # Feature 020 (T026 / R-020.10 / FR-003 / FR-006 / FR-007 / FR-008 /
    # FR-010 / data-model.md §5): four additive top-level fields.
    #
    # `evidence_gate_id` — always `"v1"` at landing (closed registry of
    # size one per R-020.2). Emits the SAME string uniformly on CPU,
    # stub-adapter, and GPU lanes (no `cpu-default` / `stub-default`
    # discrimination — see data-model.md §9). FR-014 / SC-005.
    #
    # `evidence_gate_state_counts` — aggregate state distribution across
    # the run. ALL THREE keys present (NOT sparse) per R-020.10 / MI-17.
    # Default-zero counters on every key for runs that processed zero
    # documents (stub-adapter empty corpus, etc.).
    #
    # `evidence_gate_documents` — per-doc records. Each element has
    # exactly three top-level keys (`document_id` / `decision` /
    # `signals`) and the nested `signals` object has exactly the five
    # FR-001 signal names per data-model.md §4. FR-003 PII-safety
    # closure: only signal TYPES (int / bool / float) — never raw token
    # text. Deterministic ordering per `corpus_run.py` iteration
    # (typically alphabetical by `document_id` per R-020.11).
    #
    # `evidence_gate_suppressed_fallback_count` — incremented by exactly
    # 1 per document where shape (b) suppression actually fired (the
    # four-conjunct predicate in R-020.8 returned True). Stays at 0 on
    # the legacy (no-opt-in) path. Always-emit per FR-007 / FR-008.
    #
    # MVP slice (US3, this commit): `evidence_gate_id` / `state_counts`
    # / `documents` are populated by the corpus_run / runner wiring as
    # observability. `suppressed_fallback_count` defaults to 0 and is
    # wired by the US4 skip-fallback behavior in a follow-up PR.
    evidence_gate_id: str = EVIDENCE_GATE_ID_DEFAULT
    evidence_gate_state_counts: dict[str, int] = field(
        default_factory=_default_evidence_gate_state_counts
    )
    evidence_gate_documents: list[dict[str, Any]] = field(default_factory=list)
    evidence_gate_suppressed_fallback_count: int = 0

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
            # Feature 019 additive top-level fields (T006 /
            # contracts/run-summary-schema.md §4): emitted AFTER
            # feature 018's three fields and before the closing brace
            # in fixed order. Always-emit per FR-007 / FR-008 / FR-010.
            "preprocess_strategy_id": self.preprocess_strategy_id,
            "ocr_only_fallback_count": self.ocr_only_fallback_count,
            # Feature 020 additive top-level fields (T027 / R-020.10 /
            # contracts/run-summary-schema.md): emitted in fixed order
            # AFTER feature 019's two fields and before the closing
            # brace. Always-emit per FR-008 / FR-010 / MI-16 / MI-17.
            # Per-doc `signals` shape is validated at construction time
            # in the gate's `EvidenceGateResult` — but as a defense in
            # depth at the serializer boundary, we coerce the
            # `state_counts` dict to an explicit-three-key form so a
            # buggy caller cannot leak a sparse object onto the wire.
            "evidence_gate_id": self.evidence_gate_id,
            "evidence_gate_state_counts": {
                "sufficient": int(self.evidence_gate_state_counts.get("sufficient", 0)),
                "borderline": int(self.evidence_gate_state_counts.get("borderline", 0)),
                "insufficient": int(self.evidence_gate_state_counts.get("insufficient", 0)),
            },
            "evidence_gate_documents": [
                _canonicalize_evidence_gate_record(r)
                for r in self.evidence_gate_documents
            ],
            "evidence_gate_suppressed_fallback_count": self.evidence_gate_suppressed_fallback_count,
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
