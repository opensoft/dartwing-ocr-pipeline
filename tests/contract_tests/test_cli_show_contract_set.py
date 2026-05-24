"""T070: `show contract-set` CLI subcommand."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "dartwing_ocr.validator", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_show_contract_set_json_has_required_keys() -> None:
    proc = _run("show", "contract-set", "--json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["contract_set_version"] == "1.3.0"
    for name in [
        "preprocess_output",
        "edge_extraction_output",
        "routing_decision",
        "final_structured_payload",
        "expected",
        "evaluation_document",
        "evaluation_run_summary",
        "evidence_packet",
    ]:
        assert name in payload["artifact_schemas"]
    assert len(payload["challenge_tags"]) == 18
    assert "PROVENANCE_TRIAD_INCONSISTENT" in payload["cross_artifact_rules"]


def test_show_contract_set_text_is_human_readable() -> None:
    proc = _run("show", "contract-set", "--text")
    assert proc.returncode == 0
    assert "Contract set: 1.3.0" in proc.stdout
    assert "Challenge tags" in proc.stdout
    assert "Cross-artifact rules" in proc.stdout
