"""Readiness check 8 — pipeline-runtime-timeout (T032, FR-008).

This check is a *reporter* — it does not enforce the 600 s budget itself
(the orchestrator does, via ``signal.alarm`` around the pipeline). After
the pipeline completes (or times out), the runner asks this check whether
the elapsed time stayed within budget; if yes, ``pass``; if the
orchestrator caught a ``TimeoutError``, the orchestrator sets
``context.runtime_timeout_observed = True`` and this check returns ``fail``.

Under ``--check-only`` the check is ``skipped`` (no pipeline runs).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from dartwing_ocr.gpu_demo.enums import BOUNDED_TIMEOUT_SECONDS
from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


@dataclass(frozen=True)
class PipelineRuntimeTimeoutCheck:
    """Reports whether the pipeline stayed within the bounded timeout."""

    name: str = "pipeline-runtime-timeout"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        if context.check_only:
            return ReadinessResult(
                name=self.name,
                status="skipped",
                elapsed_seconds=0.0,
            )

        start = time.monotonic()
        timed_out = getattr(context, "runtime_timeout_observed", False)
        stalled_phase = getattr(context, "stalled_phase", None)
        elapsed = time.monotonic() - start

        if not timed_out:
            return ReadinessResult(
                name=self.name,
                status="pass",
                elapsed_seconds=elapsed,
            )

        return ReadinessResult(
            name=self.name,
            status="fail",
            elapsed_seconds=elapsed,
            diagnostic=CheckDiagnostic(
                checked="Pipeline runtime",
                observed=(
                    f">{BOUNDED_TIMEOUT_SECONDS} seconds "
                    f"(stalled in phase '{stalled_phase}')"
                ),
                expected=f"<= {BOUNDED_TIMEOUT_SECONDS} seconds",
                remediation=(
                    "Inspect partial artifacts left in the per-document folder; "
                    "the stalled phase is identified in 'stalled_phase'. Check "
                    "Ollama and Paddle health."
                ),
            ),
        )
