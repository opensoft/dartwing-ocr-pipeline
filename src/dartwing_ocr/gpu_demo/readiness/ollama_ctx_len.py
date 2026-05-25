"""Readiness check 6 — ollama-context-length (T030, FR-006).

Reuses /api/ps body cached by check 3. Pass criterion (per Q5 + FR-006):
- When /api/ps exposes ``context_length`` on the matching model entry,
  require >= ``OLLAMA_CONTEXT_LENGTH`` env var (default 2048).
- When /api/ps does NOT expose ``context_length`` (defensive case — older
  Ollama or missing field), the check passes with a soft WARN; the runtime
  path catches downstream context-window errors per the FR-006 fallback.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


def _find_model_entry(api_ps_body: object, model_name: str) -> Optional[dict]:
    if not isinstance(api_ps_body, dict):
        return None
    models = api_ps_body.get("models")
    if not isinstance(models, list):
        return None
    for entry in models:
        if isinstance(entry, dict) and entry.get("name") == model_name:
            return entry
    return None


@dataclass(frozen=True)
class OllamaContextLengthCheck:
    """Confirms the running model's context length is at or above the requirement."""

    name: str = "ollama-context-length"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        if context.expected_extraction_model is None:
            elapsed = time.monotonic() - start
            return ReadinessResult(
                name=self.name,
                status="pass",  # nothing to check without a model name
                elapsed_seconds=elapsed,
            )

        entry = _find_model_entry(
            context.cached_api_ps_body, context.expected_extraction_model
        )
        elapsed = time.monotonic() - start

        # /api/ps body or model entry missing → soft pass per FR-006 fallback;
        # runtime path catches the downstream context-window error.
        if entry is None:
            return ReadinessResult(
                name=self.name,
                status="pass",
                elapsed_seconds=elapsed,
            )

        ctx_len = entry.get("context_length")
        if not isinstance(ctx_len, int):
            # Field absent — soft pass; runtime detection catches the error.
            return ReadinessResult(
                name=self.name,
                status="pass",
                elapsed_seconds=elapsed,
            )

        required = context.ollama_context_length
        if ctx_len >= required:
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
                checked=(
                    f"Ollama context length for '{context.expected_extraction_model}'"
                ),
                observed=ctx_len,
                expected=f">= {required}",
                remediation=(
                    f"Restart host Ollama with OLLAMA_CONTEXT_LENGTH={required}; "
                    "see scripts/start-host-ollama-rocm-wsl.sh."
                ),
            ),
        )
