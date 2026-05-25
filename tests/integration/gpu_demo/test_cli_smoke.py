"""Smoke tests for the GPU MVP demo CLI (T019).

These tests verify the package and CLI are importable end-to-end. They use
``subprocess.run`` so they exercise the actual ``python -m dartwing_ocr.gpu_demo``
entry point (T002 shim → T016 main). No Paddle / Ollama / pipeline composition
is required for these tests — Phase 3 lands those.
"""

from __future__ import annotations

import subprocess
import sys


def test_help_exits_zero() -> None:
    """``--help`` exits 0 and prints help text (the only stdout exception)."""
    result = subprocess.run(
        [sys.executable, "-m", "dartwing_ocr.gpu_demo", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"expected exit 0 from --help, got {result.returncode}: stderr={result.stderr!r}"
    )
    assert "dartwing-gpu-demo" in result.stdout
    assert "--check-only" in result.stdout


def test_version_exits_zero_and_prints_version() -> None:
    """``--version`` exits 0 and prints a version string."""
    result = subprocess.run(
        [sys.executable, "-m", "dartwing_ocr.gpu_demo", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"expected exit 0 from --version, got {result.returncode}: stderr={result.stderr!r}"
    )
    # argparse's --version writes to stdout in Python 3.4+; accept either stream defensively.
    combined = result.stdout + result.stderr
    assert "dartwing-gpu-demo" in combined
