"""Per-stage / per-document timing capture and run-summary serializer.

Spec FR-027. Research R-009 / R-015. Data-model `StageTiming`, `RunSummary`.

Internal arithmetic stays in integer nanoseconds (``time.monotonic_ns``).
Conversion to seconds happens only at serialization time, rounded to six
decimal places (R-015). Phase keys absent from a stage's timing map mean
"not measured" (R-009 phase-key absence policy).
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from ledgerlinc_ocr.pipeline.profiles import Stage

SCHEMA_VERSION = "0.1.0"


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
    """End-of-run JSON-Lines run summary for warm-corpus mode (R-009)."""
    stack_preset: str | None
    resolved_profiles: dict[Stage, str]
    execution_slice: dict[str, str]
    on_failure: str
    documents_total: int
    documents_succeeded: int
    documents_failed: int
    profile_initialization_seconds: dict[Stage, float] = field(default_factory=dict)
    per_document: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
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


def build_per_document_success(
    *,
    document_id: str,
    folder: str,
    timings: DocumentTimings,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "folder": folder,
        "status": "success",
        "stages": timings.to_summary_dict(),
    }


def build_per_document_failure(
    *,
    document_id: str,
    folder: str,
    failed_stage: str,
    exit_code: int,
    message: str,
    timings: DocumentTimings | None = None,
) -> dict[str, Any]:
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
