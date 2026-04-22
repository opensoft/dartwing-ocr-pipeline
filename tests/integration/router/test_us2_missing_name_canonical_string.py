"""T028 / US2 AC#1, AC#2, AC#3: missing-name routes to review with canonical
``company_name_inferred`` string (byte-exact)."""
from __future__ import annotations

from pathlib import Path


def test_missing_name_routes_to_review_with_canonical_string(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "missing_name_inferred.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["manual_review_required"] is True
    assert art["review_status"]["review_reason"] == "company_name_inferred"
    assert "company_name_inferred" in art["reasons"]


def test_missing_name_checks_reflect_inputs(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "missing_name_inferred.json")
    run_cli(folder)
    art = read_artifact(folder)
    assert art["checks"]["company_name_present"] is False
    assert art["checks"]["company_name_inferred"] is True
