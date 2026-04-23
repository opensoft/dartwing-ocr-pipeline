"""T054 / T069 / US5 FR-024: forbidden company_name provenance combinations.

Per research Decision 11: when the extractor emits a schema-valid input
that violates the company_name invariant — either ``present == true AND
inferred == true`` or ``present == false AND inferred == false`` — the
router does NOT silently correct it. Instead:

- output ``status`` = ``"partial"``
- ``decision`` = ``"edge_review_required"``
- ``reasons`` contains ``"contract_violation_detected"``
- No "quiet fix" — the input is surfaced as a contract violation for
  human attention.

T069 adds the symmetric ``present == false AND inferred == false`` case
so both forbidden combos pinned by FR-024 have executable coverage.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "fixture",
    [
        "forbidden_present_true_inferred_true.json",
        "forbidden_present_false_inferred_false.json",
    ],
)
def test_forbidden_company_name_invariant(
    tmp_path: Path, stage_fixture, run_cli, read_artifact, fixture: str
):
    folder = stage_fixture(tmp_path, fixture)
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["status"] == "partial"
    assert art["decision"] == "edge_review_required"
    assert "contract_violation_detected" in art["reasons"]
