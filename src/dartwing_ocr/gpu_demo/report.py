"""DemoRunReport dataclasses (T009).

Mirrors ``data-model.md`` §1–§5. Top-level fields are stable across all
outcomes (FR-019): unknown / non-applicable fields are emitted as explicit
null, never omitted. Cross-field invariants are mirrored as assertion tests
in ``tests/integration/gpu_demo/test_report_shape.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from dartwing_ocr.gpu_demo.enums import (
    DEMO_REPORT_KIND,
    DEMO_REPORT_SCHEMA_VERSION,
    FailureKind,
    ProbeResult,
    QualityStatus,
    QualityStatusSource,
    ReadinessCheckName,
    ReadinessCheckStatus,
    RuntimeOutcome,
    StalledPhase,
)


@dataclass(frozen=True)
class CheckDiagnostic:
    """Structured diagnostic for a failing readiness check (R-023.11)."""

    checked: str
    observed: Any  # str / int / dict / list / null — 2 KiB cap enforced at serialization
    expected: Any
    remediation: str


@dataclass(frozen=True)
class ReadinessCheck:
    """One named check from the closed FR-016 vocabulary."""

    name: ReadinessCheckName
    status: ReadinessCheckStatus  # "pass" | "fail" | "skipped"
    elapsed_seconds: float
    diagnostic: Optional[CheckDiagnostic] = None


@dataclass(frozen=True)
class ReadinessSummary:
    """Aggregated outcome of the 8-check readiness phase (FR-026)."""

    checks: list[ReadinessCheck]
    overall_passed: bool
    elapsed_seconds: float


@dataclass(frozen=True)
class PhaseTimings:
    """Wall-clock seconds per pipeline phase (FR-025). All four keys always present."""

    preprocess: Optional[float] = None
    extraction: Optional[float] = None
    routing: Optional[float] = None
    final_payload: Optional[float] = None


@dataclass(frozen=True)
class OllamaModelSnapshot:
    """Subset of an /api/ps entry used for GPU-placement verification."""

    name: str
    size: int
    size_vram: int
    context_length: Optional[int] = None


@dataclass(frozen=True)
class CPUFallbackDetection:
    """Post-run device interrogation result (R-023.15)."""

    ollama_post_run: ProbeResult
    paddle_post_run: ProbeResult
    pre_run_ollama_snapshot: Optional[dict[str, Any]] = None
    post_run_ollama_snapshot: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class DemoRunReport:
    """Single composite outcome emitted as one stdout JSON line per FR-019."""

    schema_version: str
    pipeline_version: str
    run_id: str
    interpreter_path: str
    voter_config_path: Optional[str]
    expected_extraction_model: Optional[str]
    document_folder: Optional[str]
    bounded_timeout_seconds: int
    readiness: ReadinessSummary
    runtime_outcome: Optional[RuntimeOutcome]
    stalled_phase: Optional[StalledPhase]
    failure_kind: Optional[FailureKind]
    failing_check_name: Optional[ReadinessCheckName]
    phase_timings: PhaseTimings
    total_runtime_seconds: Optional[float]
    artifact_paths: Optional[list[str]]
    quality_status: Optional[QualityStatus]
    quality_status_source: Optional[QualityStatusSource]
    cpu_fallback_detection: CPUFallbackDetection
    diagnostic: Optional[str]
    kind: str = field(default=DEMO_REPORT_KIND)


__all__ = [
    "CheckDiagnostic",
    "ReadinessCheck",
    "ReadinessSummary",
    "PhaseTimings",
    "OllamaModelSnapshot",
    "CPUFallbackDetection",
    "DemoRunReport",
    "DEMO_REPORT_SCHEMA_VERSION",
]
