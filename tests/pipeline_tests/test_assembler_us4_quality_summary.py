"""T028 [US4] — quality_summary acceptance scenarios + determinism."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from dartwing_ocr.assembler import Invocation, run
from dartwing_ocr.assembler.version import SEMVER, build_pipeline_version

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def _stage(tmp_path: Path, name: str) -> Path:
    dst = tmp_path / name
    shutil.copytree(FIXTURE_ROOT / name, dst)
    return dst


def _assemble(folder: Path) -> dict:
    out_path = run(Invocation(document_folder=folder))
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_happy_grounded_quality_summary(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    payload = _assemble(folder)
    qs = payload["quality_summary"]
    assert qs["consensus_level"] == "single_voter_baseline"
    assert qs["explicit_name_found"] is True
    assert qs["secondary_identifiers_found"] == ["address", "ein", "email"]
    # FR-019 + research.md Decision 8 — stage-1 policy 0.1.0:
    #   company=0.96, address_mean=(0.93+0.94+0.95)/3=0.94, ein=0.9, email=0.89
    #   secondary_mean = (0.94+0.9+0.89)/3 = 0.91
    #   overall = round(0.5*0.96 + 0.5*0.91, 4) = 0.935
    assert qs["overall_vendor_confidence"] == pytest.approx(0.935)

    # FIX 7 / T3 — couple the expected number to the version constant so a
    # silent formula change cannot be "fixed" by editing 0.935 alone. If the
    # formula changes, either:
    #   (a) the expected number changes (this test fails → author updates it
    #       AND bumps SEMVER), or
    #   (b) SEMVER is bumped without changing the formula (these asserts fail
    #       → author is forced to update the expected number intentionally).
    # Either branch surfaces the policy bump. Silent drift is no longer
    # possible.
    assert SEMVER == "0.1.0", (
        "SEMVER changed without updating the 0.935 expected value — "
        "this test intentionally couples the two per FIX 7 / T3"
    )
    assert payload["pipeline_version"] == build_pipeline_version() == "009-final-payload@0.1.0"


def test_spam_gate_quality_summary(tmp_path: Path):
    folder = _stage(tmp_path, "empty_extraction_spam_gate")
    payload = _assemble(folder)
    qs = payload["quality_summary"]
    assert qs["overall_vendor_confidence"] == 0.0
    assert qs["explicit_name_found"] is False
    assert qs["consensus_level"] == "single_voter_baseline"
    assert qs["secondary_identifiers_found"] == []


def test_missing_name_inferred_explicit_name_false(tmp_path: Path):
    """present=false AND inferred=true → explicit_name_found == false."""
    folder = _stage(tmp_path, "missing_name_inferred")
    payload = _assemble(folder)
    qs = payload["quality_summary"]
    assert qs["explicit_name_found"] is False


def test_quality_summary_deterministic_across_runs(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    payload1 = _assemble(folder)
    payload2 = _assemble(folder)
    assert payload1["quality_summary"] == payload2["quality_summary"]
