"""Stable-key UTF-8 single-line JSON serialization for DemoRunReport (R-023.12).

Stable order is established by the dataclass declaration order in ``report.py``
(matching the canonical order in ``contracts/demo-report-schema.md``). Wall-clock
floats are rounded to 3 dp per R-023.21 before serialization. ``CheckDiagnostic.observed``
embedded JSON blobs are truncated to ≤2 KiB at the last complete UTF-8 character
boundary per Q5 (audit walkthrough 2026-05-25).
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Optional

from dartwing_ocr.gpu_demo.report import (
    CheckDiagnostic,
    DemoRunReport,
)


_OBSERVED_BYTE_CAP = 2048  # 2 KiB cap per Q5
_TRUNCATION_SENTINEL = "… [truncated]"


def round_wall_clock(value: Optional[float]) -> Optional[float]:
    """Round a wall-clock seconds value to 3 dp (R-023.21).

    Returns ``None`` unchanged so cross-field invariants stay clean.
    """
    if value is None:
        return None
    return round(float(value), 3)


def _truncate_observed_value(value: Any) -> Any:
    """Apply the 2 KiB cap to a CheckDiagnostic.observed value (Q5).

    Strings and JSON-serializable values are converted to their JSON form and
    truncated at the last complete UTF-8 character boundary <= 2048 bytes,
    appending ``… [truncated]`` when truncation occurs. Smaller values pass
    through unchanged.
    """
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    encoded = rendered.encode("utf-8")
    if len(encoded) <= _OBSERVED_BYTE_CAP:
        return value
    # Retreat to the last complete UTF-8 character boundary <= cap.
    cut = encoded[:_OBSERVED_BYTE_CAP]
    while cut and (cut[-1] & 0xC0) == 0x80:
        cut = cut[:-1]
    truncated_str = cut.decode("utf-8", errors="ignore") + _TRUNCATION_SENTINEL
    return truncated_str


def _diagnostic_to_dict(diag: Optional[CheckDiagnostic]) -> Optional[dict[str, Any]]:
    if diag is None:
        return None
    return {
        "checked": diag.checked,
        "observed": _truncate_observed_value(diag.observed),
        "expected": diag.expected,
        "remediation": diag.remediation,
    }


def _report_to_dict(report: DemoRunReport) -> dict[str, Any]:
    """Build the canonical dict shape (declaration order matches contracts/demo-report-schema.md)."""

    return {
        "kind": report.kind,
        "schema_version": report.schema_version,
        "pipeline_version": report.pipeline_version,
        "run_id": report.run_id,
        "interpreter_path": report.interpreter_path,
        "voter_config_path": report.voter_config_path,
        "expected_extraction_model": report.expected_extraction_model,
        "document_folder": report.document_folder,
        "bounded_timeout_seconds": report.bounded_timeout_seconds,
        "readiness": {
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "elapsed_seconds": round_wall_clock(c.elapsed_seconds),
                    "diagnostic": _diagnostic_to_dict(c.diagnostic),
                }
                for c in report.readiness.checks
            ],
            "overall_passed": report.readiness.overall_passed,
            "elapsed_seconds": round_wall_clock(report.readiness.elapsed_seconds),
        },
        "runtime_outcome": report.runtime_outcome,
        "stalled_phase": report.stalled_phase,
        "failure_kind": report.failure_kind,
        "failing_check_name": report.failing_check_name,
        "phase_timings": {
            "preprocess": round_wall_clock(report.phase_timings.preprocess),
            "extraction": round_wall_clock(report.phase_timings.extraction),
            "routing": round_wall_clock(report.phase_timings.routing),
            "final_payload": round_wall_clock(report.phase_timings.final_payload),
        },
        "total_runtime_seconds": round_wall_clock(report.total_runtime_seconds),
        "artifact_paths": report.artifact_paths,
        "quality_status": report.quality_status,
        "quality_status_source": report.quality_status_source,
        "cpu_fallback_detection": dataclasses.asdict(report.cpu_fallback_detection),
        "diagnostic": report.diagnostic,
    }


def to_json_line(report: DemoRunReport) -> str:
    """Serialize a DemoRunReport to its canonical single-line JSON form.

    UTF-8, ``ensure_ascii=False``, compact separators, single line, trailing
    newline. Stable key order per the dataclass declaration order.
    """
    payload = _report_to_dict(report)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
