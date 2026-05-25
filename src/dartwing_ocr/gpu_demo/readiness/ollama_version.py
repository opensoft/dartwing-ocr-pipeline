"""Readiness check 4 — ollama-version (T028, FR-023, R-023.10).

Probes /api/version and compares against the minimum supported version
(``0.4.0`` per R-023.10 — first Ollama release with stable ``size_vram``
exposure on /api/ps). Pre-empts check 5 when ``size_vram`` would be missing
or unreliable (triage C1).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from packaging.version import InvalidVersion, Version

from dartwing_ocr.gpu_demo.enums import MIN_OLLAMA_VERSION
from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


_HTTP_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class OllamaVersionCheck:
    """Confirms running Ollama is >= MIN_OLLAMA_VERSION."""

    name: str = "ollama-version"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        url = f"{context.ollama_base_url.rstrip('/')}/api/version"
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
                    expected=f">= {MIN_OLLAMA_VERSION}",
                    remediation=(
                        f"Upgrade Ollama to >= {MIN_OLLAMA_VERSION}; see "
                        "scripts/start-host-ollama-rocm-wsl.sh."
                    ),
                ),
            )

        elapsed = time.monotonic() - start
        try:
            payload = response.json()
        except ValueError as exc:
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama {url}",
                    observed=f"non-JSON body: {exc}",
                    expected=f">= {MIN_OLLAMA_VERSION}",
                    remediation=f"Upgrade Ollama to >= {MIN_OLLAMA_VERSION}.",
                ),
            )

        raw_version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(raw_version, str):
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama {url}",
                    observed=f"missing or non-string 'version' field: {payload!r}",
                    expected=f">= {MIN_OLLAMA_VERSION}",
                    remediation=f"Upgrade Ollama to >= {MIN_OLLAMA_VERSION}.",
                ),
            )

        try:
            running = Version(raw_version)
            minimum = Version(MIN_OLLAMA_VERSION)
        except InvalidVersion:
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama {url}",
                    observed=raw_version,
                    expected=f">= {MIN_OLLAMA_VERSION}",
                    remediation=(
                        f"Upgrade Ollama to >= {MIN_OLLAMA_VERSION}; current "
                        "version string is not parseable."
                    ),
                ),
            )

        if running >= minimum:
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
                checked=f"Ollama {url}",
                observed=raw_version,
                expected=f">= {MIN_OLLAMA_VERSION}",
                remediation=(
                    f"Upgrade Ollama to >= {MIN_OLLAMA_VERSION}; see "
                    "scripts/start-host-ollama-rocm-wsl.sh."
                ),
            ),
        )
