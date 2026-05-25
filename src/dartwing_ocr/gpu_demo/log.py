"""Stderr severity-prefix helpers for the GPU MVP demo (R-023.7).

stderr lines are formatted ``<SEVERITY>:[<8-hex-prefix>] <msg>`` with
line-buffering so operators see progress in real time during the 600 s window.
Severity is a closed set: INFO / WARN / ERROR.
"""

from __future__ import annotations

import sys
from typing import TextIO

from dartwing_ocr.gpu_demo.run_id import prefix_for


_BUFFERING_CONFIGURED = False


def _ensure_line_buffering() -> None:
    """Reconfigure sys.stderr to line-buffered text mode (idempotent)."""
    global _BUFFERING_CONFIGURED
    if _BUFFERING_CONFIGURED:
        return
    try:
        sys.stderr.reconfigure(line_buffering=True)
    except (AttributeError, OSError):
        # Some test runners replace sys.stderr with a StringIO that doesn't
        # support reconfigure; fall through silently — those tests buffer
        # by line implicitly.
        pass
    _BUFFERING_CONFIGURED = True


def _emit(severity: str, run_id: str, msg: str, stream: TextIO | None = None) -> None:
    _ensure_line_buffering()
    target = stream if stream is not None else sys.stderr
    target.write(f"{severity}:[{prefix_for(run_id)}] {msg}\n")


def info(run_id: str, msg: str, *, stream: TextIO | None = None) -> None:
    """Emit an ``INFO:[<run_id>] <msg>`` line to stderr."""
    _emit("INFO", run_id, msg, stream=stream)


def warn(run_id: str, msg: str, *, stream: TextIO | None = None) -> None:
    """Emit a ``WARN:[<run_id>] <msg>`` line to stderr."""
    _emit("WARN", run_id, msg, stream=stream)


def error(run_id: str, msg: str, *, stream: TextIO | None = None) -> None:
    """Emit an ``ERROR:[<run_id>] <msg>`` line to stderr."""
    _emit("ERROR", run_id, msg, stream=stream)
