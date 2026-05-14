"""T052 — FR-024: inputs never mutated, success or failure branch."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"

# Every file we ever stage (some fixtures supply a subset).
INPUT_FILENAMES = (
    "edge_extraction_output.json",
    "routing_decision.json",
    "preprocess_output.json",
    "expected.json",
    "notes.md",
    "source.pdf",
)


def _stage_with_extras(tmp_path: Path, fixture_name: str) -> Path:
    dst = tmp_path / fixture_name
    shutil.copytree(FIXTURE_ROOT / fixture_name, dst)
    # Drop in the optional siblings so the read-only invariant covers them too.
    (dst / "preprocess_output.json").write_text('{"_stub": true}\n', encoding="utf-8")
    (dst / "expected.json").write_text('{"_stub": true}\n', encoding="utf-8")
    (dst / "notes.md").write_text("stub\n", encoding="utf-8")
    (dst / "source.pdf").write_bytes(b"%PDF-1.4\nstub\n")
    return dst


def _hash_tree(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in INPUT_FILENAMES:
        p = folder / name
        if p.is_file():
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _run_cli(folder: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "dartwing_ocr.assembler",
         "--document-folder", str(folder)],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize("fixture,expected_exit", [
    ("happy_grounded", 0),
    ("contract_drift", 2),
    ("document_id_mismatch", 2),
    ("routing_contradiction", 2),
    ("schema_invalid_extractor", 2),
    ("missing_name_inferred", 0),
    ("empty_extraction_spam_gate", 0),
])
def test_inputs_byte_identical_after_run(tmp_path: Path, fixture: str, expected_exit: int):
    folder = _stage_with_extras(tmp_path, fixture)
    before = _hash_tree(folder)
    result = _run_cli(folder)
    after = _hash_tree(folder)
    assert result.returncode == expected_exit
    assert before == after, (
        "input files must be byte-identical before/after a run "
        f"(fixture={fixture}, exit={result.returncode})"
    )
