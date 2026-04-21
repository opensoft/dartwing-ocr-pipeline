"""T020 / US1 AC#5: reasons traceability.

- edge_accept emits at least one affirmative entry (FR-016).
- edge_review_required has review_status.review_reason == highest-priority
  forcing entry in reasons (exhaustive coverage lands in US3).
"""
from __future__ import annotations

import json
from pathlib import Path

AFFIRMATIVES = frozenset({
    "company_name_explicit",
    "spam_gate_passed",
    "secondary_identifier_floor_met",
    "upstream_extraction_ok",
})


def test_edge_accept_reasons_contains_affirmative(
    green_fixture: Path, run_cli, read_artifact
):
    run_cli(green_fixture)
    art = read_artifact(green_fixture)
    assert art["decision"] == "edge_accept"
    assert AFFIRMATIVES.intersection(art["reasons"])


def test_review_reason_is_first_forcing_entry(
    tmp_path: Path, fixture_dir: Path, run_cli, read_artifact
):
    base = json.loads(
        (fixture_dir / "clean_explicit_name_full_identity.json").read_text()
    )
    base["vendor_candidate"]["company_name"] = {
        "value": "Guessed Acme",
        "present": False,
        "inferred": True,
        "confidence": 0.3,
        "evidence": ["p0_b1"],
    }
    (tmp_path / "edge_extraction_output.json").write_text(json.dumps(base))

    run_cli(tmp_path)
    art = read_artifact(tmp_path)
    assert art["review_status"]["review_reason"] == art["reasons"][0]
