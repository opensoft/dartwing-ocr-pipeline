"""T052 / US5 AC#5 clarification: bad-status inputs still emit schema-valid output.

Partial / failure inputs are soft errors — the router still emits a
``routing_decision.json`` that passes ``routing_decision.schema.json``.
``status: "partial" | "failure"`` is a value, not a schema violation.
"""
from __future__ import annotations

from pathlib import Path

from dartwing_ocr.validator import validate_artifact


def _validate_output(folder: Path) -> None:
    outcome = validate_artifact(
        folder / "routing_decision.json",
        "routing_decision",
        version="1.0.0",
    )
    assert outcome.passed, [v.reason for v in outcome.violations]


def test_partial_input_output_is_schema_valid(
    tmp_path: Path, stage_fixture, run_cli
):
    folder = stage_fixture(tmp_path, "partial_upstream.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    _validate_output(folder)


def test_failure_input_output_is_schema_valid(
    tmp_path: Path, stage_fixture, run_cli
):
    folder = stage_fixture(tmp_path, "failure_upstream.json")
    result = run_cli(folder)
    assert result.returncode == 0, result.stderr
    _validate_output(folder)
