"""T035 / US3 AC#1, AC#2, AC#3: secondary-identifier floor (>= 2)."""
from __future__ import annotations

from pathlib import Path


def test_zero_secondaries_routes_to_review(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "explicit_name_zero_secondaries.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["review_reason"] == (
        "secondary_identifiers_insufficient"
    )
    assert "secondary_identifiers_insufficient" in art["reasons"]


def test_one_secondary_routes_to_review(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "explicit_name_one_secondary.json")
    run_cli(folder)
    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["review_reason"] == (
        "secondary_identifiers_insufficient"
    )


def test_two_secondaries_route_to_accept(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "explicit_name_two_secondaries.json")
    run_cli(folder)
    art = read_artifact(folder)
    assert art["decision"] == "edge_accept"
    assert art["review_status"]["manual_review_required"] is False
    # Address + email = 2 floor slots.
    assert art["checks"]["address_has_minimum_components"] is True
    assert art["checks"]["website_or_email_present"] is True
