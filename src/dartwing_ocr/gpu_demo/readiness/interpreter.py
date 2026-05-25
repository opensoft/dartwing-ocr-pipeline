"""Readiness check 1 — interpreter/venv (T025, FR-002 + FR-003)."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


_EXPECTED_VENV_NAMES: tuple[str, ...] = (
    ".venv-paddle-rocm",
    ".venv-paddle-dcu",  # established successor name; per FR-002 wording
)


@dataclass(frozen=True)
class InterpreterVenvCheck:
    """Validates the running interpreter sits inside the Paddle ROCm venv."""

    name: str = "interpreter/venv"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        interpreter = os.path.realpath(sys.executable)
        ok = any(name in interpreter for name in _EXPECTED_VENV_NAMES)
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
