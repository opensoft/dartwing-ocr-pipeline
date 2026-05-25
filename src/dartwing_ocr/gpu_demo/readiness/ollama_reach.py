"""Readiness check 3 — ollama-reachability (T027).

HTTP GET ``OLLAMA_BASE_URL/api/ps`` with a 2-second timeout (well below the
10-second aggregate readiness budget per R-023.4). On success, caches the
parsed JSON body in ``ReadinessResult.side_channel`` so downstream checks
(``ollama-model-gpu-placement``, ``ollama-context-length``) avoid a second
network round-trip.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


_HTTP_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class OllamaReachabilityCheck:
    """Confirms host Ollama is reachable at OLLAMA_BASE_URL."""

    name: str = "ollama-reachability"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        url = f"{context.ollama_base_url.rstrip('/')}/api/ps"
        try:
            response = httpx.get(url, timeout=_HTTP_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            elapsed = time.monotonic() - start
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama {url}",
                    observed=f"{type(exc).__name__}: {exc}",
                    expected="HTTP 200 with parseable JSON body",
                    remediation=(
                        "Start host Ollama: scripts/start-host-ollama-rocm-wsl.sh"
                    ),
                ),
            )

        elapsed = time.monotonic() - start
        if response.status_code != 200:
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama {url}",
                    observed=f"HTTP {response.status_code}",
                    expected="HTTP 200 with parseable JSON body",
                    remediation=(
                        "Check host Ollama is running and accepting requests."
                    ),
                ),
            )

        try:
            body = response.json()
        except ValueError as exc:
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama {url}",
                    observed=f"non-JSON body: {exc}",
                    expected="HTTP 200 with parseable JSON body",
                    remediation=(
                        "Check host Ollama version compatibility with /api/ps."
                    ),
                ),
            )

        return ReadinessResult(
            name=self.name,
            status="pass",
            elapsed_seconds=elapsed,
            side_channel=body,
        )
