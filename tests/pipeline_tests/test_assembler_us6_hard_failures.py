"""T039 [US6] — hard-fail acceptance scenarios AS-1..AS-6."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def _run_cli(folder: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.assembler",
         "--document-folder", str(folder)],
        capture_output=True, text=True,
    )


def _hash_inputs(folder: Path) -> dict[str, str]:
    names = ("edge_extraction_output.json", "routing_decision.json")
    return {
        n: hashlib.sha256((folder / n).read_bytes()).hexdigest()
        for n in names
        if (folder / n).is_file()
    }


def _parse_stderr_json(stderr: str) -> dict:
    # Pick the last non-empty line that is a JSON object.
    for line in reversed(stderr.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    pytest.fail(f"no JSON error line in stderr: {stderr!r}")


def _assert_no_output(folder: Path) -> None:
    assert not (folder / "final_structured_payload.json").exists()


@pytest.mark.parametrize("fixture,expected_kind,expected_exit", [
    ("contract_drift", "contract_drift", 2),
    ("document_id_mismatch", "document_id_mismatch", 2),
    ("routing_contradiction", "routing_contradiction", 2),
    ("schema_invalid_extractor", "schema_invalid_input", 2),
])
def test_hard_failure_fixture(tmp_path: Path, fixture: str, expected_kind: str, expected_exit: int):
    folder = _stage(tmp_path, fixture)
    before = _hash_inputs(folder)
    result = _run_cli(folder)
    after = _hash_inputs(folder)

    assert result.returncode == expected_exit
    assert before == after, "inputs must not be mutated"
    _assert_no_output(folder)
    err = _parse_stderr_json(result.stderr)
    assert err["status"] == "error"
    assert err["kind"] == expected_kind


def test_missing_extractor_input(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    (folder / "edge_extraction_output.json").unlink()
    result = _run_cli(folder)
    assert result.returncode == 2
    _assert_no_output(folder)
    err = _parse_stderr_json(result.stderr)
    assert err["kind"] == "missing_input"


def test_missing_routing_input(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    (folder / "routing_decision.json").unlink()
    result = _run_cli(folder)
    assert result.returncode == 2
    _assert_no_output(folder)
    err = _parse_stderr_json(result.stderr)
    assert err["kind"] == "missing_input"
