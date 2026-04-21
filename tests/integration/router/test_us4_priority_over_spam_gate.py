"""T043 / US4 AC#4: missing-name outranks spam-gate in FR-015 priority.

Construct: ``company_name.value == null`` + ``inferred == true`` + every
other vendor_candidate field null. Both spam-gate (structural-null) and
missing-name (inferred=true) fire; ``review_reason`` is still
``"company_name_inferred"`` and the reasons array orders them
``[company_name_inferred, post_extraction_spam_gate_failed, ...]``.
"""
from __future__ import annotations

import json
from pathlib import Path


def _build_fixture(tmp_path: Path, fixture_dir: Path) -> Path:
    base = json.loads((fixture_dir / "all_null_spam.json").read_text())
    base["vendor_candidate"]["company_name"] = {
        "value": None,
        "present": False,
        "inferred": True,
        "confidence": 0.2,
        "evidence": [],
    }
    base["document_id"] = "inv_302_missing_name_over_spam"
    (tmp_path / "edge_extraction_output.json").write_text(json.dumps(base))
    return tmp_path


def test_missing_name_beats_spam_gate(
    tmp_path: Path, fixture_dir: Path, run_cli, read_artifact
):
    folder = _build_fixture(tmp_path, fixture_dir)
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr

    art = read_artifact(folder)
    assert art["decision"] == "edge_review_required"
    assert art["review_status"]["review_reason"] == "company_name_inferred"

    reasons = art["reasons"]
    assert "company_name_inferred" in reasons
    assert "post_extraction_spam_gate_failed" in reasons
    assert reasons.index("company_name_inferred") < reasons.index(
        "post_extraction_spam_gate_failed"
    )
