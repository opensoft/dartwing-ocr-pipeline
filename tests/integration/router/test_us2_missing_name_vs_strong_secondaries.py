"""T029 / US2 AC#4: overwhelming secondaries do NOT override missing-name.

FR-015 priority 1 beats secondary-identifier floor satisfaction.
"""
from __future__ import annotations

from pathlib import Path


def test_strong_secondaries_do_not_override_missing_name(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    folder = stage_fixture(tmp_path, "missing_name_with_strong_secondaries.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["review_reason"] == "company_name_inferred"
    # Floor IS met — but it must not win.
    assert art["checks"]["address_has_minimum_components"] is True
    assert art["checks"]["at_least_one_tax_id_present"] is True
    assert art["checks"]["website_or_email_present"] is True
