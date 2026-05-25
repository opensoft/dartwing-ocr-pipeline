"""Readiness check 5 — ollama-model-gpu-placement (T029, FR-005).

Reuses the /api/ps body cached by check 3 (ollama-reachability) via the
``context.cached_api_ps_body`` field that the runner threads through.
Pass criterion: matching model entry exists AND ``size_vram > 0`` AND
``size_vram == size`` (strict equality, no tolerance).
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
    """Return the matching /api/ps model dict, or None."""
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
class OllamaPlacementCheck:
    """Confirms the configured extraction model is fully GPU-placed."""

    name: str = "ollama-model-gpu-placement"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        if context.expected_extraction_model is None:
            elapsed = time.monotonic() - start
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked="Ollama /api/ps for the configured model",
                    observed=None,
                    expected="model name from voter config",
                    remediation=(
                        "voter config did not yield a model name — check the "
                        "voter-config loader."
                    ),
                ),
            )

        entry = _find_model_entry(
            context.cached_api_ps_body, context.expected_extraction_model
        )
        elapsed = time.monotonic() - start

        if entry is None:
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=f"Ollama /api/ps for model '{context.expected_extraction_model}'",
                    observed=None,
                    expected=(
                        f"entry with name '{context.expected_extraction_model}' present"
                    ),
                    remediation=(
                        f"Load the model: ollama pull {context.expected_extraction_model} "
                        "or ensure it is referenced before the demo runs."
                    ),
                ),
            )

        size = entry.get("size")
        size_vram = entry.get("size_vram")
        if not isinstance(size, int) or not isinstance(size_vram, int):
            return ReadinessResult(
                name=self.name,
                status="fail",
                elapsed_seconds=elapsed,
                diagnostic=CheckDiagnostic(
                    checked=(
                        f"GPU placement of '{context.expected_extraction_model}'"
                    ),
                    observed={"size": size, "size_vram": size_vram},
                    expected="size_vram (int) > 0 AND size_vram == size (int)",
                    remediation=(
                        "Upgrade Ollama; /api/ps must expose integer size and size_vram."
                    ),
                ),
            )

        if size_vram > 0 and size_vram == size:
            return ReadinessResult(
                name=self.name,
                status="pass",
                elapsed_seconds=elapsed,
                # NOTE: do NOT publish side_channel here — the runner uses
                # side_channel to refresh cached_api_ps_body, and downstream
                # checks (ollama-context-length) require the full /api/ps body
                # (a dict with "models" list), not just the matched entry.
            )

        return ReadinessResult(
            name=self.name,
            status="fail",
            elapsed_seconds=elapsed,
            diagnostic=CheckDiagnostic(
                checked=f"GPU placement of '{context.expected_extraction_model}'",
                observed={"size": size, "size_vram": size_vram},
                expected="size_vram > 0 AND size_vram == size",
                remediation=(
                    "Restart Ollama on a fresh GPU context; the model is partially "
                    "or fully on CPU."
                ),
            ),
        )
