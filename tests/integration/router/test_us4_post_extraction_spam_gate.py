"""T041 / US4 AC#1, AC#2, AC#5: post-extraction spam gate."""
from __future__ import annotations

import pytest

from pathlib import Path


def test_all_null_fires_spam_gate(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "all_null_spam.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["checks"]["post_extraction_spam_gate_passed"] is False
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["review_reason"] == (
        "post_extraction_spam_gate_failed"
    )


def test_all_null_overall_score_is_zero(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "all_null_spam.json")
    run_cli(folder)
    art = read_artifact(folder)
    assert art["scores"]["overall_vendor_identity_score"] == pytest.approx(0.0)
    for key in ("company_name_score", "address_score",
                "tax_id_score", "contact_score"):
        assert art["scores"][key] == pytest.approx(0.0)


def test_green_path_passes_spam_gate(
    green_fixture: Path, run_cli, read_artifact
):
    run_cli(green_fixture)
    art = read_artifact(green_fixture)
    assert art["checks"]["post_extraction_spam_gate_passed"] is True
    assert "post_extraction_spam_gate_failed" not in art["reasons"]
