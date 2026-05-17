"""Feature 020 / T054 / FR-016 / R-020.14 / R-020.15 / SC-008: GPU two-metric
quality-gate verdict producing Appendix B numbers.

Marked ``@pytest.mark.gpu`` and **deferrable per R-020.15** — GPU workstation
hardware is required to produce the legacy- and candidate-run
``evaluation_run_summary.json`` files this test compares. Two
independent mechanisms keep this test from executing on a non-GPU
host:

1. The default CI invocation uses pytest's ``-m "not gpu"`` expression.
   Marker expressions filter AFTER collection — these tests are
   collected, then deselected before execution, so they show up as
   ``deselected`` in the pytest summary line rather than running.
2. ``tests/conftest.py`` contributes a runtime ``skip`` for every
   ``gpu``-marked test whenever the cached preflight state is not
   ``ppstructurev3_init_succeeded``. That state covers every non-happy
   path: CPU-only hosts, hosts without Paddle installed, hosts where
   Paddle is installed but GPU-bind fails, and hosts where the
   preflight import itself crashes (FR-001 / FR-019). The skip reason
   traces back to the FR-001 state.

The test executes only when BOTH conditions allow it: the ``-m`` filter
does not exclude ``gpu`` (or no ``-m`` is set) AND preflight resolved
to ``ppstructurev3_init_succeeded`` on a working GPU host. When that
happens, the current body raises ``pytest.fail`` so the deferred-
implementation state surfaces loudly the moment GPU verification is
attempted; the follow-up replaces the body with the real two-metric
comparison.

Two-metric promotion gate (FR-016 / R-020.14 / SC-008) — field names
match ``contracts/stage1_vendor_identity/v1.2.0/evaluation_run_summary.schema.json``:

- ``candidate overall_metrics.vendor_identity_pass_rate >= legacy
  overall_metrics.vendor_identity_pass_rate``
- ``candidate sum(documents[].overall_passed) >= legacy
  sum(documents[].overall_passed)`` (the per-document pass count is
  derived by summing the per-doc boolean flags)

If EITHER metric regresses, this test **fails** (does NOT skip) so a
failing promotion candidate is visibly rejected; T057's default-flip is
gated on a passing verdict here. The promotion direction is one-way:
quality may improve or stay flat, never regress.

Inputs (over the same fixed 5-doc subset as T053 — see
``test_evidence_gate_benchmark.py`` for the subset lookup procedure):

- Legacy run: omit ``--evidence-gate-skip-fallback`` entirely AND
  ensure ``LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK`` is unset (or set
  to ``""`` / ``"0"`` / any falsy value per R-020.1). The CLI uses
  ``argparse store_true`` for the flag, so there is NO
  ``--no-evidence-gate-skip-fallback`` counterpart — absence of the
  flag IS the off-state. Emits ``evaluation_run_summary.json`` over
  the subset.
- Candidate run: pass ``--evidence-gate-skip-fallback`` (opt-in
  active). Emits ``evaluation_run_summary.json`` over the same subset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu


def test_quality_gate_two_metric_evidence_gate_gpu(tmp_path: Path) -> None:
    """GPU two-metric verdict: compare legacy and candidate
    ``evaluation_run_summary.json`` files; assert candidate >= legacy
    on BOTH the per-corpus aggregate vendor-identity score AND the
    per-document pass count.

    The assertion shape (executed when the GPU deferral is closed),
    using the actual field names from
    ``contracts/stage1_vendor_identity/v1.2.0/evaluation_run_summary.schema.json``:

    .. code-block:: python

        legacy = json.loads(
            (legacy_run_dir / "evaluation_run_summary.json").read_text()
        )
        candidate = json.loads(
            (candidate_run_dir / "evaluation_run_summary.json").read_text()
        )

        # FR-016 Metric (1): per-corpus aggregate vendor-identity score.
        # The evaluator emits a vendor-identity pass-rate under
        # `overall_metrics.vendor_identity_pass_rate` (0.0-1.0 float).
        legacy_score = float(legacy["overall_metrics"]["vendor_identity_pass_rate"])
        candidate_score = float(
            candidate["overall_metrics"]["vendor_identity_pass_rate"]
        )

        # FR-016 Metric (2): per-document pass count. The evaluator
        # emits per-document `overall_passed` flags in `documents[]`;
        # the count is derived by summing the booleans.
        legacy_pass = sum(1 for d in legacy["documents"] if d["overall_passed"])
        candidate_pass = sum(1 for d in candidate["documents"] if d["overall_passed"])

        assert candidate_score >= legacy_score, (
            f"FR-016 / R-020.14 regression: candidate vendor-identity score "
            f"{candidate_score:.4f} < legacy {legacy_score:.4f}"
        )
        assert candidate_pass >= legacy_pass, (
            f"FR-016 / R-020.14 regression: candidate per-document pass "
            f"count {candidate_pass} < legacy {legacy_pass}"
        )

    Failure (NOT skip) on regression is intentional per SC-008.

    On a CPU host this body is unreachable thanks to the module-level
    `pytestmark = pytest.mark.gpu` (see `tests/conftest.py`). On a GPU
    host the `pytest.fail` below catches the deferred-implementation
    state — the deferred GPU run replaces this body with the real
    comparison loop and updates `research.md` Appendix B with the
    recorded verdict.
    """
    _ = tmp_path
    pytest.fail(
        "GPU quality-gate verdict deferred per R-020.15; wire the "
        "two-metric comparison (vendor_identity_pass_rate + "
        "per-document overall_passed sum) when the workstation GPU is "
        "available."
    )
