"""Feature 020 / T054 / FR-016 / R-020.14 / R-020.15 / SC-008: GPU two-metric
quality-gate verdict producing Appendix B numbers.

Marked ``@pytest.mark.gpu`` and **deferrable per R-020.15** — GPU workstation
hardware is required to produce the legacy- and candidate-run
``evaluation_run_summary.json`` files this test compares. On a CPU-only
host (the default suite filter ``-m "not gpu"`` deselects this file) the
test is collected but never executes. When the deferred GPU run is
performed in a follow-up, the ``@pytest.mark.skip`` decorator can be
removed and the body will read both summaries and assert the FR-016
two-metric promotion gate.

Two-metric promotion gate (FR-016 / R-020.14 / SC-008):

- ``candidate aggregate_vendor_identity_field_score >= legacy
  aggregate_vendor_identity_field_score``
- ``candidate per_document_pass_count >= legacy per_document_pass_count``

If EITHER metric regresses, this test **fails** (does NOT skip) so a
failing promotion candidate is visibly rejected; T057's default-flip is
gated on a passing verdict here. The promotion direction is one-way:
quality may improve or stay flat, never regress.

Inputs (over the same fixed 5-doc subset as T053 — see
``test_evidence_gate_benchmark.py`` for the subset lookup procedure):

- Legacy run: ``--no-evidence-gate-skip-fallback`` (or absence /
  ``LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=`` unset). Emits
  ``evaluation_run_summary.json`` over the subset.
- Candidate run: ``--evidence-gate-skip-fallback`` (opt-in active).
  Emits ``evaluation_run_summary.json`` over the same subset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu


@pytest.mark.skip(
    reason=(
        "GPU two-metric quality-gate verdict; deferrable per R-020.15. "
        "Requires the workstation GPU + the legacy- and candidate-run "
        "`evaluation_run_summary.json` artifacts produced by the FR-015 "
        "benchmark in T053. Run manually via "
        "`pytest -m gpu tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py` "
        "on the workstation; on pass, T057 may flip the default; on "
        "fail, the default stays off and the failure is recorded in "
        "`research.md` Appendix B."
    )
)
def test_quality_gate_two_metric_evidence_gate_gpu(tmp_path: Path) -> None:
    """GPU two-metric verdict: compare legacy and candidate
    ``evaluation_run_summary.json`` files; assert candidate >= legacy
    on BOTH the per-corpus aggregate vendor-identity field score AND
    the per-document pass count.

    The assertion shape (executed when the GPU deferral is closed):

    .. code-block:: python

        legacy = json.loads(legacy_run_dir / "evaluation_run_summary.json")
        candidate = json.loads(candidate_run_dir / "evaluation_run_summary.json")

        legacy_score = float(legacy["aggregate_vendor_identity_field_score"])
        candidate_score = float(candidate["aggregate_vendor_identity_field_score"])
        legacy_pass = int(legacy["per_document_pass_count"])
        candidate_pass = int(candidate["per_document_pass_count"])

        assert candidate_score >= legacy_score, (
            f"FR-016 / R-020.14 regression: candidate aggregate field score "
            f"{candidate_score:.4f} < legacy {legacy_score:.4f}"
        )
        assert candidate_pass >= legacy_pass, (
            f"FR-016 / R-020.14 regression: candidate per-document pass "
            f"count {candidate_pass} < legacy {legacy_pass}"
        )

    Failure (NOT skip) on regression is intentional per SC-008.
    """
    # Body intentionally fails when run on GPU without an updated
    # implementation that produces both run-summary inputs. At PR
    # landing time on a CPU host this is unreachable thanks to the
    # module-level `pytestmark = pytest.mark.gpu` + `@pytest.mark.skip`
    # above. The deferred GPU run replaces this body with the real
    # comparison loop, removes the skip decorator, and updates
    # research.md Appendix B with the verdict.
    pytest.fail(
        "GPU quality-gate verdict deferred per R-020.15; remove "
        "@pytest.mark.skip and wire the two-metric comparison when the "
        "workstation GPU is available."
    )
