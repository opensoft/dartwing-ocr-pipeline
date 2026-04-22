"""T033 [US5] — trace block references upstream artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ledgerlinc_ocr.assembler import Invocation, run

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def _assemble(folder: Path) -> dict:
    out_path = run(Invocation(document_folder=folder))
    return json.loads(out_path.read_text(encoding="utf-8"))


EXPECTED_TRACE = {
    "source_file": "source.pdf",
    "preprocess_output_file": "preprocess_output.json",
    "edge_extraction_output_file": "edge_extraction_output.json",
    "routing_decision_file": "routing_decision.json",
}


def test_trace_values_match_documented_filenames(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    payload = _assemble(folder)
    assert payload["trace"] == EXPECTED_TRACE


def test_trace_paths_are_relative(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    payload = _assemble(folder)
    for key in EXPECTED_TRACE:
        val = payload["trace"][key]
        assert "/" not in val
        assert not Path(val).is_absolute()


def test_source_file_named_even_when_absent(tmp_path: Path):
    """Spec Edge Case §7 — trace still names source.pdf when the file isn't there."""
    folder = _stage(tmp_path, "happy_grounded")
    assert not (folder / "source.pdf").exists()
    payload = _assemble(folder)
    assert payload["trace"]["source_file"] == "source.pdf"


def test_trace_paths_resolve_when_files_exist(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n")
    (folder / "preprocess_output.json").write_text("{}", encoding="utf-8")
    payload = _assemble(folder)
    for key in (
        "source_file", "preprocess_output_file",
        "edge_extraction_output_file", "routing_decision_file",
    ):
        assert (folder / payload["trace"][key]).exists()
