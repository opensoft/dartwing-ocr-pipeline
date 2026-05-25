"""Post-run device interrogation for silent CPU-fallback detection (T062, R-023.15).

Runs two best-effort probes after the pipeline completes:
1. Ollama ``/api/ps`` re-query for the same model identity.
2. Paddle device re-invocation via feature 014's preflight.

Each probe has a 2 s wall-clock timeout; combined budget is 5 s. Result
values are ``"consistent"`` / ``"fell_back"`` / ``"unreachable"`` / ``"skipped"``.
The orchestrator interprets these per R-023.15:
- ``fell_back`` → rewrite ``runtime_outcome`` to ``failed_at_extraction`` with
  ``failure_kind = "cpu-fallback-detected"`` (SC-004 enforcement).
- ``unreachable`` → keep ``runtime_outcome`` but set
  ``failure_kind = "post-run-interrogation-unreachable"`` (best-effort, not confirmed).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from dartwing_ocr.gpu_demo.enums import ProbeResult


_PROBE_TIMEOUT_SECONDS = 2.0
_AGGREGATE_BUDGET_SECONDS = 5.0


def _probe_ollama_post_run(
    ollama_base_url: str,
    model_name: str,
    pre_run_snapshot: Optional[dict[str, Any]],
) -> tuple[ProbeResult, Optional[dict[str, Any]]]:
    """Re-query /api/ps and compare placement vs pre-run snapshot.

    The verdict is built from two checks:

    1. Post-run placement: ``size_vram == size`` AND ``size_vram > 0``
       (current state is fully GPU-placed).
    2. Pre-vs-post consistency (only when ``pre_run_snapshot`` is provided):
       the post-run ``size_vram`` must match the pre-run ``size_vram``.

    Both checks must succeed for the probe to report ``"consistent"``. Either
    a current CPU placement OR a drop between pre and post counts as
    ``"fell_back"``. (Triage M3: previously ``pre_run_snapshot`` was accepted
    but never compared.)
    """
    url = f"{ollama_base_url.rstrip('/')}/api/ps"
    try:
        response = httpx.get(url, timeout=_PROBE_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        return "unreachable", None

    if response.status_code != 200:
        return "unreachable", None
    try:
        body = response.json()
    except ValueError:
        return "unreachable", None

    if not isinstance(body, dict):
        return "unreachable", None
    models = body.get("models")
    if not isinstance(models, list):
        return "unreachable", None
    entry = None
    for candidate in models:
        if isinstance(candidate, dict) and candidate.get("name") == model_name:
            entry = candidate
            break
    if entry is None:
        # Model no longer loaded — treat as fallback (Ollama dropped it).
        return "fell_back", None

    size = entry.get("size")
    size_vram = entry.get("size_vram")
    if not isinstance(size, int) or not isinstance(size_vram, int):
        return "unreachable", entry
    # M3: compare against pre-run snapshot when available; any drop in
    # `size_vram` from pre→post counts as fall-back even if current placement
    # is full-GPU (catches a model that was reloaded mid-run on CPU then
    # bounced back to GPU).
    if isinstance(pre_run_snapshot, dict):
        pre_size_vram = pre_run_snapshot.get("size_vram")
        if isinstance(pre_size_vram, int) and pre_size_vram > size_vram:
            return "fell_back", entry
    if size_vram > 0 and size_vram == size:
        return "consistent", entry
    return "fell_back", entry


def _probe_paddle_post_run() -> ProbeResult:
    """Re-invoke feature 014's preflight; consistent iff still GPU-ready."""
    try:
        from dartwing_ocr.preprocessing import preflight as preflight_mod
    except ImportError:
        return "unreachable"

    try:
        readout = preflight_mod.classify(attempt_ppstructurev3_init=True)
    except Exception:  # noqa: BLE001 — defensive
        return "unreachable"

    success_state = preflight_mod.PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
    if readout.state == success_state:
        return "consistent"
    return "fell_back"


@dataclass(frozen=True)
class CPUFallbackOutcome:
    """Aggregated CPU-fallback outcome consumed by the orchestrator."""

    ollama_post_run: ProbeResult
    paddle_post_run: ProbeResult
    pre_run_ollama_snapshot: Optional[dict[str, Any]] = None
    post_run_ollama_snapshot: Optional[dict[str, Any]] = None
    fell_back: bool = False
    unreachable: bool = False
    budget_exceeded: bool = False


def interrogate(
    *,
    ollama_base_url: str,
    expected_model: str,
    pre_run_snapshot: Optional[dict[str, Any]] = None,
) -> CPUFallbackOutcome:
    """Run the two post-run probes within the aggregate budget."""
    start = time.monotonic()

    ollama_result, post_snapshot = _probe_ollama_post_run(
        ollama_base_url, expected_model, pre_run_snapshot
    )

    elapsed = time.monotonic() - start
    if elapsed >= _AGGREGATE_BUDGET_SECONDS:
        # K3 (triage / R-023.15): combined budget exceeded → BOTH probes
        # marked "unreachable"; CPU-fallback detection is inconclusive. The
        # orchestrator reads ``budget_exceeded`` and emits the prescribed
        # WARN line. Keeping the actual Ollama probe result here would
        # produce a misleading verdict ("we ran out of time AND we know X").
        return CPUFallbackOutcome(
            ollama_post_run="unreachable",
            paddle_post_run="unreachable",
            pre_run_ollama_snapshot=pre_run_snapshot,
            post_run_ollama_snapshot=post_snapshot,
            fell_back=False,
            unreachable=True,
            budget_exceeded=True,
        )

    paddle_result = _probe_paddle_post_run()

    fell_back = ollama_result == "fell_back" or paddle_result == "fell_back"
    unreachable = (
        ollama_result == "unreachable" or paddle_result == "unreachable"
    ) and not fell_back

    return CPUFallbackOutcome(
        ollama_post_run=ollama_result,
        paddle_post_run=paddle_result,
        pre_run_ollama_snapshot=pre_run_snapshot,
        post_run_ollama_snapshot=post_snapshot,
        fell_back=fell_back,
        unreachable=unreachable,
        budget_exceeded=False,
    )
