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


# --------------------------------------------------------------------------
# FIX 4 / T1 — pre-existing payload must NEVER be overwritten on failure.
#
# US1 AS-5 (and the constitution's determinism principle) require that a
# failed run leave any pre-existing `final_structured_payload.json` exactly
# as it was — byte-for-byte. The existing "no output written" assertion
# alone isn't enough: it assumes the folder started clean. The sentinel
# tests below seed a distinctive byte string AFTER staging, run the failing
# invocation, and confirm the file is unchanged.
# --------------------------------------------------------------------------

SENTINEL_BYTES = (
    b'{"SENTINEL": "do not overwrite", "marker": "FIX4-T1-pre-existing-payload"}\n'
)


def _seed_sentinel_payload(folder: Path) -> Path:
    p = folder / "final_structured_payload.json"
    p.write_bytes(SENTINEL_BYTES)
    return p


def _assert_sentinel_intact(folder: Path) -> None:
    p = folder / "final_structured_payload.json"
    assert p.exists(), "sentinel file disappeared — pre-existing payload was deleted"
    assert p.read_bytes() == SENTINEL_BYTES, (
        "pre-existing final_structured_payload.json was modified on failure"
    )


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


# --------------------------------------------------------------------------
# FIX 2 / C1 — `unreadable_input` is a DISTINCT error kind from both
# `missing_input` (file absent) and `schema_invalid_input` (parses but
# violates schema). FR-003b requires the three kinds to be distinguishable.
# Previously untested: malformed-bytes inputs silently could have been
# classified wrong without any test catching it.
# --------------------------------------------------------------------------

UNREADABLE_PAYLOADS = [
    ("empty", b""),
    ("truncated_json", b"{not json"),
    ("binary_garbage", b"\x00\x01\x02\x03\xff\xfe"),
]


@pytest.mark.parametrize("target_file", ["edge_extraction_output.json", "routing_decision.json"])
@pytest.mark.parametrize("label,payload", UNREADABLE_PAYLOADS, ids=[p[0] for p in UNREADABLE_PAYLOADS])
def test_unreadable_input_kind(tmp_path: Path, target_file: str, label: str, payload: bytes):
    """Malformed bytes must be reported as kind=unreadable_input, exit 2, no output."""
    folder = _stage(tmp_path, "happy_grounded")
    (folder / target_file).write_bytes(payload)
    result = _run_cli(folder)

    assert result.returncode == 2, (
        f"expected exit 2 for {target_file} with {label!r}, got {result.returncode}; "
        f"stderr={result.stderr!r}"
    )
    _assert_no_output(folder)
    err = _parse_stderr_json(result.stderr)
    assert err["status"] == "error"
    assert err["kind"] == "unreadable_input", (
        f"expected kind=unreadable_input for {target_file} with {label!r}, got {err!r}"
    )


# --------------------------------------------------------------------------
# FIX 4 / T1 — parametrized sentinel tests covering ALL SIX hard-fail modes.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fixture,expected_kind", [
    ("contract_drift", "contract_drift"),
    ("document_id_mismatch", "document_id_mismatch"),
    ("routing_contradiction", "routing_contradiction"),
    ("schema_invalid_extractor", "schema_invalid_input"),
])
def test_hard_failure_does_not_overwrite_pre_existing_payload(
    tmp_path: Path, fixture: str, expected_kind: str
):
    folder = _stage(tmp_path, fixture)
    _seed_sentinel_payload(folder)
    result = _run_cli(folder)

    assert result.returncode == 2
    err = _parse_stderr_json(result.stderr)
    assert err["kind"] == expected_kind
    _assert_sentinel_intact(folder)


def test_missing_extractor_does_not_overwrite_pre_existing_payload(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    (folder / "edge_extraction_output.json").unlink()
    _seed_sentinel_payload(folder)
    result = _run_cli(folder)

    assert result.returncode == 2
    err = _parse_stderr_json(result.stderr)
    assert err["kind"] == "missing_input"
    _assert_sentinel_intact(folder)


def test_missing_routing_does_not_overwrite_pre_existing_payload(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    (folder / "routing_decision.json").unlink()
    _seed_sentinel_payload(folder)
    result = _run_cli(folder)

    assert result.returncode == 2
    err = _parse_stderr_json(result.stderr)
    assert err["kind"] == "missing_input"
    _assert_sentinel_intact(folder)
