"""T018 / US1 AC#3: consensus_summary pinned to single_voter_baseline."""
from __future__ import annotations

from pathlib import Path


def test_consensus_summary_exact_shape(
    green_fixture: Path, run_cli, read_artifact
):
    run_cli(green_fixture)
    artifact = read_artifact(green_fixture)
    assert artifact["consensus_summary"] == {
        "mode": "single_voter_baseline",
        "agreement_level": "not_applicable",
    }
