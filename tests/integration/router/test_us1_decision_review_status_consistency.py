"""T019 / US1 AC#4: decision/review_status mutual consistency.

Green-path → edge_accept + (manual_review_required=false, review_reason=null).
Inline missing-name variant → edge_review_required + (true, "company_name_inferred").
"""
from __future__ import annotations

import json
from pathlib import Path


def _write_missing_name(tmp_path: Path, fixture_dir: Path) -> Path:
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
    return tmp_path


def test_accept_has_null_review_reason(
    green_fixture: Path, run_cli, read_artifact
):
    run_cli(green_fixture)
    art = read_artifact(green_fixture)
    assert art["decision"] == "edge_accept"
    assert art["review_status"]["manual_review_required"] is False
    assert art["review_status"]["review_reason"] is None


def test_review_required_has_non_null_review_reason(
    tmp_path: Path, fixture_dir: Path, run_cli, read_artifact
):
    folder = _write_missing_name(tmp_path, fixture_dir)
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["manual_review_required"] is True
    assert art["review_status"]["review_reason"] == "company_name_inferred"
