"""Readiness check 1 — interpreter/venv (T025, FR-002 + FR-003)."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


_EXPECTED_VENV_NAMES: frozenset[str] = frozenset({
    ".venv-paddle-rocm",
    ".venv-paddle-dcu",  # established successor name; per FR-002 wording
})


@dataclass(frozen=True)
class InterpreterVenvCheck:
    """Validates the running interpreter sits inside the Paddle ROCm venv."""

    name: str = "interpreter/venv"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        interpreter = os.path.realpath(sys.executable)
        # L1 (triage): match against path components, not substring. A
        # substring match accepted any path containing the venv name as
        # a fragment (e.g. ``/home/x/.venv-paddle-rocm-backup/bin/python``).
        ok = bool(_EXPECTED_VENV_NAMES.intersection(Path(interpreter).parts))
        elapsed = time.monotonic() - start
        if ok:
            return ReadinessResult(
                name=self.name,
                status="pass",
                elapsed_seconds=elapsed,
            )
        diagnostic = CheckDiagnostic(
            checked="Python interpreter path",
            observed=interpreter,
            expected=f"path under one of {list(_EXPECTED_VENV_NAMES)}",
            remediation=(
                "Activate the Paddle ROCm venv: source .venv-paddle-rocm/bin/activate"
            ),
        )
        return ReadinessResult(
            name=self.name,
            status="fail",
            elapsed_seconds=elapsed,
            diagnostic=diagnostic,
        )
