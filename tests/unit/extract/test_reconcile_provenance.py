"""T049 — reconcile step 5 (company_name provenance override)."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from ledgerlinc_ocr.extract.config import load_voter_config
from ledgerlinc_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"
_US3_MISSING = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us3_missing_name"


def _load(folder: Path, response_name: str):
    packet = json.loads((folder / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((folder / response_name).read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(folder / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return packet, parsed, config


def _run(packet, parsed, config):
    return reconcile(
        packet=packet,
        parsed=parsed,
        config=config,
        now=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
        pipeline_version="0.0.0-test+provenance",
        repair_trail=[],
    )


def test_evidence_non_empty_sets_present_true_inferred_false() -> None:
    packet, parsed, config = _load(_US1, "voter_response_clean.json")
    out = _run(packet, parsed, config)
    cn = out["vendor_candidate"]["company_name"]
    assert cn["evidence"] != []
    assert cn["present"] is True
    assert cn["inferred"] is False


def test_evidence_empty_sets_present_false_inferred_true_regardless_of_model_claim() -> None:
    packet, parsed, config = _load(_US3_MISSING, "voter_response_guess_with_present_true.json")
    assert parsed["vendor_candidate"]["company_name"]["present"] is True
    out = _run(packet, parsed, config)
    cn = out["vendor_candidate"]["company_name"]
    assert cn["evidence"] == []
    assert cn["present"] is False
    assert cn["inferred"] is True


def test_override_recorded_in_extraction_notes() -> None:
    packet, parsed, config = _load(_US3_MISSING, "voter_response_guess_with_present_true.json")
    out = _run(packet, parsed, config)
    blob = "\n".join(out["extraction_notes"])
    assert "company_name" in blob


def test_xor_invariant_holds_both_cases() -> None:
    for fixture, resp in [
        (_US1, "voter_response_clean.json"),
        (_US3_MISSING, "voter_response_guess_with_present_true.json"),
    ]:
        packet, parsed, config = _load(fixture, resp)
        out = _run(packet, parsed, config)
        cn = out["vendor_candidate"]["company_name"]
        assert cn["present"] != cn["inferred"], f"{fixture} XOR violated"


def test_override_ignores_present_false_claim_when_evidence_present() -> None:
    # Model claims present=false but evidence grounds the name → present=true, inferred=false.
    packet, parsed, config = _load(_US1, "voter_response_clean.json")
    parsed = copy.deepcopy(parsed)
    parsed["vendor_candidate"]["company_name"]["present"] = False
    parsed["vendor_candidate"]["company_name"]["inferred"] = True
    out = _run(packet, parsed, config)
    cn = out["vendor_candidate"]["company_name"]
    assert cn["evidence"] != []
    assert cn["present"] is True
    assert cn["inferred"] is False
