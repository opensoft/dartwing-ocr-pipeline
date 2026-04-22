"""T050 / US5 AC#3: status=failure input.

Per research Decision 11 + FR-020, a ``status == "failure"`` input is
mapped to ``status == "partial"`` on output (so the artifact is still a
schema-valid narrative), ``decision == "edge_review_required"`` with
``review_reason == "upstream_extraction_failed"``, and the upstream
failure is named in ``reasons``.
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
    # Missing-name and spam-gate both also fire on this fixture, but
    # upstream-failure must appear in reasons per FR-015 traceability.
    assert "upstream_extraction_failed" in art["reasons"]
