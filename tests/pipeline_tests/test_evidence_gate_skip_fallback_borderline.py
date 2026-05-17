"""Feature 020 / T034 / R-020.15: GPU end-to-end borderline test.

Deferred per R-020.15. CPU-safe coverage of the same MI-11 invariant
lives in T034a (``test_evidence_gate_skip_fallback_borderline_cpu.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu


@pytest.mark.skip(reason="GPU end-to-end; deferrable per R-020.15.")
def test_skip_fallback_borderline_runs_fallback_gpu(tmp_path: Path) -> None:
    """A `borderline` candidate runs the FR-005 fallback and the recorded
    decision is over the post-fallback output."""
