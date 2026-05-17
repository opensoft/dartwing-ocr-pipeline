"""Feature 020 / T034 / FR-024 / R-020.15: GPU end-to-end borderline test
asserting MI-11 invariant.

Marked `@pytest.mark.gpu` and deferrable per R-020.15. Same setup as
T033 (`test_evidence_gate_skip_fallback.py`) but on a `borderline`-
eligible fixture. Asserts:

- `evidence_gate_suppressed_fallback_count == 0` (gate said borderline
  on the OCR-only candidate, so suppression did NOT fire per MI-14)
- `ocr_only_fallback_count == 1` (FR-005 fallback ran)
- `evidence_gate_documents[0]` records the gate decision over the
  POST-fallback PPStructureV3 output (MI-11 / R-020.7)

CPU-safe coverage of the same MI-11 invariant lives in T034a
(`test_evidence_gate_skip_fallback_borderline_cpu.py`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu


@pytest.mark.skip(
    reason=(
        "GPU end-to-end run; deferrable per R-020.15. Requires a "
        "`borderline`-eligible fixture (page-1 header band with some "
        "but not all sufficiency signals) AND a `ppstructurev3` "
        "fallback that re-OCRs the page producing a different decision "
        "post-fallback. CPU-safe variant in "
        "`test_evidence_gate_skip_fallback_borderline_cpu.py` (T034a)."
    )
)
def test_skip_fallback_borderline_runs_fallback_gpu(tmp_path: Path) -> None:
    """GPU smoke test: a `borderline`-eligible document under
    `--preprocess-strategy=ocr-only-v1 --evidence-gate-skip-fallback`
    runs the FR-005 PPStructureV3 fallback AND the recorded gate
    decision is over the post-fallback output."""
    pytest.fail("GPU fixture-dependent test; see module-level skip reason.")
