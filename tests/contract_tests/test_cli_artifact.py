"""T028: CLI `validate artifact` paths + exit codes + --json/--text modes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORT_SCHEMA = json.loads(
    (
        _REPO_ROOT
        / "specs"
        / "001-freeze-schemas-folder-contracts"
        / "contracts"
        / "report.schema.json"
    ).read_text(encoding="utf-8")
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.validator", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_good_fixture_exits_zero(good_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "artifact",
        str(good_fixtures_root / "edge_extraction_output.json"),
        "--contract",
        "edge_extraction_output",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bad_fixture_exits_one(bad_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "artifact",
        str(bad_fixtures_root / "empty_string_for_null.json"),
        "--contract",
        "edge_extraction_output",
    )
    assert proc.returncode == 1


def test_json_output_conforms_to_report_schema(
    bad_fixtures_root: Path,
) -> None:
    proc = _run(
        "validate",
        "artifact",
        str(bad_fixtures_root / "empty_string_for_null.json"),
        "--contract",
        "edge_extraction_output",
        "--json",
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    errors = list(Draft202012Validator(_REPORT_SCHEMA).iter_errors(payload))
    assert errors == []
    assert payload["passed"] is False
    assert any(
        v["violation_code"] == "NULL_VS_EMPTY_STRING" for v in payload["violations"]
    )


def test_text_output_contains_code_and_path(bad_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "artifact",
        str(bad_fixtures_root / "tax_id_invalid_type.json"),
        "--contract",
        "edge_extraction_output",
    )
    assert proc.returncode == 1
    assert "TAX_ID_TYPE_INVALID" in proc.stdout
    assert "/vendor_candidate/tax_ids" in proc.stdout


def test_usage_error_exits_two() -> None:
    proc = _run(
        "validate",
        "artifact",
        "/does/not/exist.json",
        "--contract",
        "not_a_real_contract",
    )
    assert proc.returncode == 2
