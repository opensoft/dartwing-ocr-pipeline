"""T038 / US3 AC#6: priority ordering missing-name > secondary-floor.

When both rules fire, ``reasons`` contains both canonical strings in
``[company_name_inferred, secondary_identifiers_insufficient]`` order per
FR-015; ``review_reason == "company_name_inferred"``.
"""
from __future__ import annotations

from pathlib import Path


def test_both_rules_fire_priority_order(
    tmp_path: Path, stage_fixture, run_cli, read_artifact
):
    # missing_name_inferred.json has inferred name AND only 1 floor slot
    # (city+state+postal_code); both rules fire.
    folder = stage_fixture(tmp_path, "missing_name_inferred.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["review_reason"] == "company_name_inferred"

    reasons = art["reasons"]
    assert "company_name_inferred" in reasons
    assert "secondary_identifiers_insufficient" in reasons
    # FR-015 order: missing-name comes before secondary-floor.
    assert reasons.index("company_name_inferred") < reasons.index(
        "secondary_identifiers_insufficient"
    )
