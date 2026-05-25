"""Stderr severity-prefix helpers for the GPU MVP demo (R-023.7).

stderr lines are formatted ``<SEVERITY>:[<8-hex-prefix>] <msg>`` with
line-buffering so operators see progress in real time during the 600 s window.
Severity is a closed set: INFO / WARN / ERROR.
"""

from __future__ import annotations

import re
import sys
from typing import TextIO

from dartwing_ocr.gpu_demo.run_id import prefix_for


_BUFFERING_CONFIGURED = False

# S2 (triage): strip control characters from interpolated values so an Ollama
# model name or operator-supplied path containing \n / \r / \x1b cannot forge
# stderr lines (terminal spoof) or inject ANSI escapes. Strips C0 controls
# (0x00-0x1F) except printable tab (0x09), the DEL byte (0x7F), and the ANSI
# CSI introducer (0x1B). The terminating newline written by _emit is NOT in
# msg — it's appended after sanitization.
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def _sanitize(msg: str) -> str:
    """Replace control characters with a Unicode replacement marker.

    Idempotent and safe for already-sanitized strings. ``\\t`` is preserved
    because operators rely on tab-aligned diagnostics in JSON-ish output.
    """
    if not isinstance(msg, str):
        msg = str(msg)
    return _CONTROL_CHAR_PATTERN.sub("�", msg)


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
    target.write(f"{severity}:[{prefix_for(run_id)}] {_sanitize(msg)}\n")


def info(run_id: str, msg: str, *, stream: TextIO | None = None) -> None:
    """Emit an ``INFO:[<run_id>] <msg>`` line to stderr."""
    _emit("INFO", run_id, msg, stream=stream)


def warn(run_id: str, msg: str, *, stream: TextIO | None = None) -> None:
    """Emit a ``WARN:[<run_id>] <msg>`` line to stderr."""
    _emit("WARN", run_id, msg, stream=stream)


def error(run_id: str, msg: str, *, stream: TextIO | None = None) -> None:
    """Emit an ``ERROR:[<run_id>] <msg>`` line to stderr."""
    _emit("ERROR", run_id, msg, stream=stream)
