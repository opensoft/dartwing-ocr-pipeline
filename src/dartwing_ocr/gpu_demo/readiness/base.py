"""ReadinessCheck protocol + context/result dataclasses (T012).

Each per-check module implements a ``ReadinessCheck`` (a callable with the
``Protocol`` signature below). The runner threads a ``ReadinessContext``
through the fixed-order vocabulary and accumulates ``ReadinessResult``
instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol

from dartwing_ocr.gpu_demo.enums import (
    ReadinessCheckName,
    ReadinessCheckStatus,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


@dataclass(frozen=True)
class ReadinessContext:
    """Shared input to every readiness check.

    The context is built once per run after argparse + voter-config loading.
    Per-check modules consume only the fields they need; downstream checks
    (e.g. ``ollama-model-gpu-placement``) re-use cached probe results stored
    by earlier checks via the orchestrator (the runner does not own that
    cache — the orchestrator passes the cached ``/api/ps`` body into the
    relevant check's run kwargs).
    """

    run_id: str
    interpreter_path: str
    voter_config_path: Optional[str]
    expected_extraction_model: Optional[str]
    document_folder: Optional[Path]
    ollama_base_url: str
    ollama_context_length: int
    check_only: bool
    cached_api_ps_body: Any = None  # populated by ollama-reachability check; consumed by 5+6
    # R2-11 (round-2 triage): post-pipeline timeout state used to live behind
    # an `object.__setattr__` frozen-bypass hack — the same anti-pattern B3
    # was supposed to retire. Promote to proper Optional fields so the
    # post-pipeline check reads them via attribute access against an
    # immutable replace()-built context.
    runtime_timeout_observed: bool = False
    stalled_phase: Optional[str] = None


@dataclass(frozen=True)
class ReadinessResult:
    """Outcome of a single readiness check."""

    name: ReadinessCheckName
    status: ReadinessCheckStatus
    elapsed_seconds: float
    diagnostic: Optional[CheckDiagnostic] = None
    # Optional side-channel payload the check may publish for downstream
    # checks (e.g. ollama-reachability publishes the cached /api/ps body).
    side_channel: Any = None


class ReadinessCheck(Protocol):
    """Protocol every readiness check implements.

    The name attribute pins the closed-vocabulary identifier; the ``run``
    method performs the probe and returns a ``ReadinessResult``.
    """

    name: ReadinessCheckName

    def run(self, context: ReadinessContext) -> ReadinessResult:  # pragma: no cover - protocol
        ...
