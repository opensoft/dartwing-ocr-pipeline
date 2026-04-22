"""T051 / US5 AC#4, AC#5, SC-006: hard-error exit codes.

Missing file / unreadable file / schema-invalid JSON / version-drift all
exit non-zero (code 2 per the CLI contract), write NO
``routing_decision.json``, and emit a human-readable cause on stderr.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest


def _assert_no_artifact(folder: Path) -> None:
    assert not (folder / "routing_decision.json").exists(), (
        "hard-error path must not write routing_decision.json"
    )


def test_missing_input_file_is_hard_error(
    tmp_path: Path, run_cli
):
    # tmp_path is a valid folder but has no edge_extraction_output.json
    result = run_cli(tmp_path)
    assert result.returncode != 0
    assert result.returncode == 2
    assert result.stderr.strip(), "must emit a human-readable cause on stderr"
    _assert_no_artifact(tmp_path)


def test_missing_folder_is_hard_error(tmp_path: Path, run_cli):
    ghost = tmp_path / "does-not-exist"
    result = run_cli(ghost)
    assert result.returncode == 2
    assert result.stderr.strip()
    # Cannot assert absence of a file in a folder that doesn't exist; this
    # is implicit.


def test_schema_invalid_json_is_hard_error(tmp_path: Path, run_cli):
    # Valid JSON, but not a schema-valid edge_extraction_output.
    (tmp_path / "edge_extraction_output.json").write_text(
        json.dumps({"contract_set_version": "1.0.0", "nonsense": True})
    )
    result = run_cli(tmp_path)
    assert result.returncode == 2
    assert result.stderr.strip()
    _assert_no_artifact(tmp_path)


def test_non_json_bytes_is_hard_error(tmp_path: Path, run_cli):
    (tmp_path / "edge_extraction_output.json").write_text("not json at all {{")
    result = run_cli(tmp_path)
    assert result.returncode == 2
    assert result.stderr.strip()
    _assert_no_artifact(tmp_path)


def test_version_drift_is_hard_error(
    tmp_path: Path, stage_fixture, run_cli
):
    folder = stage_fixture(tmp_path, "version_drift.json")
    result = run_cli(folder)
    assert result.returncode == 2
    # Cause should mention the version or contract_set_version.
    assert "version" in result.stderr.lower() or "1.0.0" in result.stderr
    _assert_no_artifact(folder)


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX permission semantics only"
)
def test_unreadable_input_is_hard_error(
    tmp_path: Path, stage_fixture, run_cli
):
    folder = stage_fixture(tmp_path, "clean_explicit_name_full_identity.json")
    input_path = folder / "edge_extraction_output.json"
    orig_mode = input_path.stat().st_mode
    try:
        # If running as root (common in devcontainers), chmod 000 does NOT
        # prevent reads. Skip the assertion in that case rather than
        # emitting a false negative.
        if os.geteuid() == 0:
            pytest.skip("running as root; chmod does not enforce read denial")
        input_path.chmod(0)
        result = run_cli(folder)
        assert result.returncode == 2
        assert result.stderr.strip()
        _assert_no_artifact(folder)
    finally:
        input_path.chmod(orig_mode | stat.S_IRUSR)
