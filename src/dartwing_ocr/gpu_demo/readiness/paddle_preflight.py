"""Readiness check 2 — paddle-rocm-preflight (T026 + Q7).

Composes feature 014's Paddle ROCm preflight (``preprocessing.preflight.classify``)
in-process. Distinguishes two failure shapes per audit walkthrough Q7:
- ImportError / ModuleNotFoundError → wheel not installed
- state != PPSTRUCTUREV3_INIT_SUCCEEDED → wheel imports but device unusable
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


@dataclass(frozen=True)
class PaddleRocmPreflightCheck:
    """Confirms Paddle ROCm preflight reports the GPU-ready state."""

    name: str = "paddle-rocm-preflight"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()

        # Import-time failure shape (wheel not installed).
        try:
            from dartwing_ocr.preprocessing import preflight as preflight_mod
        except ImportError as exc:
            elapsed = time.monotonic() - start
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked="Paddle ROCm wheel import",
                    observed={"import_error": f"{type(exc).__name__}: {exc}"},
                    expected="paddlepaddle_dcu importable from active venv",
                    remediation=(
                        "Install paddlepaddle-dcu in .venv-paddle-rocm "
                        "(it is not currently importable)."
                    ),
                ),
            )

        # Device-check failure shape (wheel installed but state != success).
        try:
            readout = preflight_mod.classify(attempt_ppstructurev3_init=True)
        except Exception as exc:  # noqa: BLE001 — preflight may raise its own taxonomy
            elapsed = time.monotonic() - start
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked="Paddle ROCm preflight",
                    observed={"preflight_error": f"{type(exc).__name__}: {exc}"},
                    expected="feature 014 preflight returns PPSTRUCTUREV3_INIT_SUCCEEDED",
                    remediation=(
                        "Re-install Paddle ROCm wheel and verify ROCm exposure."
                    ),
                ),
            )

        elapsed = time.monotonic() - start
        success_state = preflight_mod.PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED

        if readout.state == success_state:
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
                checked="Paddle device backend",
                observed={"import_ok": True, "state": readout.state.value},
                expected="ppstructurev3_init_succeeded",
                remediation=(
                    readout.recommendation
                    or "Reinstall paddlepaddle-dcu in .venv-paddle-rocm; verify ROCm exposure."
                ),
            ),
        )
