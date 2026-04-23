"""T023 [US3] — review_status propagates verbatim."""

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


def test_accept_review_reason_null(tmp_path: Path):
    folder = _stage(tmp_path, "happy_grounded")
    payload = _assemble(folder)
    assert payload["review_status"] == {
        "manual_review_required": False, "review_reason": None,
    }


def test_company_name_inferred_exact_string(tmp_path: Path):
    folder = _stage(tmp_path, "missing_name_inferred")
    payload = _assemble(folder)
    assert payload["review_status"] == {
        "manual_review_required": True, "review_reason": "company_name_inferred",
    }


def test_spam_gate_review_reason(tmp_path: Path):
    folder = _stage(tmp_path, "empty_extraction_spam_gate")
    payload = _assemble(folder)
    assert payload["review_status"] == {
        "manual_review_required": True, "review_reason": "post_extraction_spam_gate_failed",
    }


def test_unknown_review_reason_propagates(tmp_path: Path):
    """Spec Edge Case §3: arbitrary strings must not be normalized."""
    folder = _stage(tmp_path, "happy_grounded")
    # Mutate the routing file to carry a novel reason + flip to review-required.
    routing_path = folder / "routing_decision.json"
    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    routing["decision"] = "edge_review_required"
    routing["review_status"] = {
        "manual_review_required": True, "review_reason": "custom_reason_zzz",
    }
    routing_path.write_text(json.dumps(routing), encoding="utf-8")

    payload = _assemble(folder)
    assert payload["review_status"]["review_reason"] == "custom_reason_zzz"
