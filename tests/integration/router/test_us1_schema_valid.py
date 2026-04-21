"""T017 / US1 AC#1 + AC#2: CLI emits a schema-valid routing_decision.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ISO_UTC_Z_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_cli_exits_zero_and_writes_schema_valid_artifact(
    green_fixture: Path, run_cli
):
    result = run_cli(green_fixture)
    assert result.returncode == 0, result.stderr
    artifact_path = green_fixture / "routing_decision.json"
    assert artifact_path.exists()

    from ledgerlinc_ocr.validator import validate_artifact

    outcome = validate_artifact(
        artifact_path, "routing_decision", version="1.0.0"
    )
    assert outcome.passed, outcome.violations


def test_cli_artifact_field_shape(green_fixture: Path, run_cli, read_artifact):
    run_cli(green_fixture)
    artifact = read_artifact(green_fixture)
    assert artifact["contract_set_version"] == "1.0.0"
    assert artifact["document_id"] == "inv_001_easy"
    assert artifact["pipeline_version"]
    assert artifact["policy_version"]
    assert ISO_UTC_Z_SECOND.match(artifact["processed_at"])


def test_cli_stdout_is_single_json_line(green_fixture: Path, run_cli):
    result = run_cli(green_fixture)
    assert result.returncode == 0
    lines = [l for l in result.stdout.splitlines() if l]
    assert len(lines) == 1
    envelope = json.loads(lines[0])
    assert envelope["status"] == "ok"
    assert envelope["document_id"] == "inv_001_easy"
    assert envelope["decision"] == "edge_accept"
