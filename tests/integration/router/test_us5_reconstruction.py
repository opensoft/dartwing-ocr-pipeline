"""T053 / US5 AC#6, SC-005, SC-009: decision reconstruction from output alone.

SC-005: The ``routing_decision.json`` is a self-contained audit trail. With
only the output artifact and the documented rule set (canonical reason
strings + priority order), the ``decision`` MUST be reconstructable
without access to the input. This test is the machine-readable form of
that property.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dartwing_ocr.router import reasons as R

FORCING_REASONS = set(R.FORCING_PRIORITY)
CONTRACT_VIOLATION_REASON = (
    R.INFORMATIONAL_CONTRACT_VIOLATION_PRESENT_INFERRED_BOTH_TRUE
)


def _reconstruct_decision(artifact: dict) -> str:
    """Documented rule: any forcing reason OR contract-violation → review."""
    reasons = artifact["reasons"]
    if any(r in FORCING_REASONS for r in reasons):
        return "edge_review_required"
    if CONTRACT_VIOLATION_REASON in reasons:
        return "edge_review_required"
    return "edge_accept"


@pytest.mark.parametrize(
    "fixture_name",
    [
        "clean_explicit_name_full_identity.json",
        "missing_name_inferred.json",
        "explicit_name_two_secondaries.json",
        "all_null_spam.json",
        "partial_upstream.json",
        "failure_upstream.json",
    ],
)
def test_decision_reconstructs_from_output_alone(
    tmp_path: Path,
    stage_fixture,
    run_cli,
    read_artifact,
    fixture_name: str,
):
    folder = stage_fixture(tmp_path, fixture_name)
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    art = read_artifact(folder)
    reconstructed = _reconstruct_decision(art)
    assert reconstructed == art["decision"], (
        f"policy_version={art.get('policy_version')} "
        f"reasons={art.get('reasons')} "
        f"written={art['decision']} reconstructed={reconstructed}"
    )
