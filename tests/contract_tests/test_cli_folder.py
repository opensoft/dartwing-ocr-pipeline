"""T048: CLI `validate folder` path + exit codes + --json/--text."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ledgerlinc_ocr.validator", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_good_folder_exits_zero(good_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "folder",
        str(good_fixtures_root / "folders" / "inv_001_easy"),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bad_folder_exits_one(bad_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "folder",
        str(bad_fixtures_root / "folders" / "inv_003_hard"),
    )
    assert proc.returncode == 1


def test_folder_json_output_has_counts(bad_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "folder",
        str(bad_fixtures_root / "folders" / "inv_003_hard"),
        "--json",
    )
    payload = json.loads(proc.stdout)
    assert payload["passed"] is False
    assert payload["counts"]["error"] >= 1
    assert payload["target_summary"].startswith("folder:")


def test_easy_missing_notes_passes_with_warning(bad_fixtures_root: Path) -> None:
    proc = _run(
        "validate",
        "folder",
        str(bad_fixtures_root / "folders" / "inv_004_easy"),
        "--json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["passed"] is True
    assert payload["counts"]["warning"] == 1
    assert payload["warnings"][0]["violation_code"] == "FOLDER_NOTES_MISSING_SOFT"
