"""CheckDiagnostic → stderr-line projection (T052, R-023.11).

Renders a ``CheckDiagnostic`` to the canonical stderr line shape:

    readiness check '<name>' failed — observed <observed>, expected <expected>. Remediation: <remediation>

The orchestrator emits this via ``log.error(run_id, line)`` so each failing
readiness check surfaces the same content on both stderr and the JSON line.
"""

from __future__ import annotations

from dartwing_ocr.gpu_demo.report import CheckDiagnostic


def format_diagnostic_line(check_name: str, diagnostic: CheckDiagnostic) -> str:
    """Format a CheckDiagnostic as a one-line stderr message (R-023.11)."""
    return (
        f"readiness check '{check_name}' failed — "
        f"observed {diagnostic.observed!r}, expected {diagnostic.expected!r}. "
        f"Remediation: {diagnostic.remediation}"
    )
