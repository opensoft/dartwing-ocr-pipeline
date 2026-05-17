"""Feature 020 / T033 / R-020.15: GPU end-to-end skip-fallback test.

Deferred per R-020.15. CPU-safe coverage of the same invariants lives in
``test_evidence_gate_skip_fallback_borderline_cpu.py`` and
``test_evidence_gate_recorded_over_final.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu


@pytest.mark.skip(reason="GPU end-to-end; deferrable per R-020.15.")
def test_skip_fallback_sufficient_suppresses_ppstructurev3_gpu(
    tmp_path: Path,
) -> None:
    """A `sufficient`-eligible doc keeps the OCR-only output AND
    increments the suppression counter under `--evidence-gate-skip-fallback`."""
