"""T050 / US5 AC#3: status=failure input.

Per research Decision 11 + FR-020, a ``status == "failure"`` input is
mapped to ``status == "partial"`` on output (so the artifact is still a
schema-valid narrative), ``decision == "edge_review_required"`` with
``review_reason == "upstream_extraction_failed"``, and the upstream
failure is named in ``reasons``.

Decision 11 is explicit that **no other rules are evaluated** on a
failure input — the extractor's structural booleans are untrustworthy,
so ``upstream_extraction_failed`` MUST be the sole forcing reason.
Anything less strict would allow a lower-priority reason (e.g.,
``post_extraction_spam_gate_failed``, which the all-null fixture would
otherwise trip) to preempt the upstream-failure signal in
``review_reason`` via FR-015 priority ordering.
"""
from __future__ import annotations

from pathlib import Path


def test_failure_input_is_reviewed_and_named(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "failure_upstream.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    art = read_artifact(folder)
    # Research Decision 11 pins failure→partial mapping; regression here
    # would misrepresent router-run status, not just widen the schema enum.
    assert art["status"] == "partial"
    assert art["decision"] == "edge_review_required"
    # Decision 11 short-circuit: upstream_extraction_failed MUST be the sole
    # forcing reason and MUST be the review_reason — not preempted by any
    # other forcing signal derived from the untrustworthy input booleans.
    assert art["review_status"]["review_reason"] == "upstream_extraction_failed"
    assert art["reasons"] == ["upstream_extraction_failed"], (
        "Decision 11 mandates 'no other rules are evaluated' on failure "
        f"inputs; extra reasons indicate short-circuit regression: {art['reasons']}"
    )
