"""T054 / US5 FR-024: forbidden ``present == true AND inferred == true``.

Per research Decision 11: when the extractor emits a schema-valid input
that violates the company_name invariant (both present and inferred
true), the router does NOT silently correct it. Instead:

- output ``status`` = ``"partial"``
- ``decision`` = ``"edge_review_required"``
- ``reasons`` contains ``"contract_violation_detected"``
- No "quiet fix" — the input is surfaced as a contract violation for
  human attention.
"""
from __future__ import annotations

from pathlib import Path


def test_forbidden_present_inferred_both_true(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(
        tmp_path, "forbidden_present_true_inferred_true.json"
    )
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["status"] == "partial"
    assert art["decision"] == "edge_review_required"
    assert "contract_violation_detected" in art["reasons"]
