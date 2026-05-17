"""T082-T084 — stub-path corpus walk (SC-001, SC-002, SC-003).

The stage-1 corpus under `tests/stage1_vendor_identity/inv_*` is authored by a
separate workstream. These tests run the stub voter against every folder that
carries a `preprocess_output.json` and assert the slice-level invariants that
are testable without Gemma on the real corpus. They auto-skip when the corpus
is empty so CI passes pre-corpus; once folders are added the walk is live.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from dartwing_ocr.extract.cli import main as extract_main
from dartwing_ocr.validator import ArtifactName, validate_artifact

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _REPO_ROOT / "tests" / "stage1_vendor_identity"
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"
_EVIDENCE_ID = re.compile(r"^p\d+_[bl]\d+$")


def _corpus_folders() -> list[Path]:
    if not _CORPUS.exists():
        return []
    return sorted(
        p for p in _CORPUS.glob("inv_*")
        if (p / "preprocess_output.json").is_file()
    )


def _missing_name_folders() -> list[Path]:
    return [p for p in _corpus_folders() if "missing_name" in p.name]


def _write_stub_config(folder: Path, response_name: str = "voter_response.json") -> Path:
    cfg = {
        "voter_id": "stub@corpus_walk",
        "voter_role": "primary_extractor",
        "consensus_mode": "single_voter_baseline",
        "model_runtime": {
            "provider": "stub",
            "model_name": "stub-voter",
            "model_version": "0",
            "runtime": "in-process-fixture",
        },
        "ollama": {"model_tag": "unused", "timeout_seconds": 1.0, "connect_timeout_seconds": 1.0},
        "sampling": {"temperature": 0.0, "seed": 0, "top_p": None, "top_k": None},
        "prompt": {"template_path": "stub_noop.md", "max_output_tokens": 1, "format": None},
        "reconciliation": {"ungrounded_confidence_cap": 0.30},
        "x_fixture_path": response_name,
    }
    path = folder / "voter_config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    (folder / "stub_noop.md").write_text(
        "Stub voter does not use prompt content.\n", encoding="utf-8"
    )
    return path


def _write_canned_response(folder: Path, *, present: bool, evidence_for_name: bool) -> None:
    """Write a stub canned response that either claims a grounded company_name
    (for general schema walk) or an ungrounded guess (for the missing-name walk)."""

    base = json.loads((_US1 / "voter_response_clean.json").read_text(encoding="utf-8"))
    response = copy.deepcopy(base)
    if not evidence_for_name:
        response["vendor_candidate"]["company_name"]["evidence"] = []
        response["vendor_candidate"]["company_name"]["value"] = "Generated Guess"
    (folder / "voter_response.json").write_text(
        json.dumps(response, indent=2), encoding="utf-8"
    )


def _run_stub(tmp_path: Path, src: Path, evidence_for_name: bool) -> Path:
    dest = tmp_path / src.name
    shutil.copytree(src, dest)
    # Remove any pre-existing edge_extraction_output from a previous run.
    (dest / "edge_extraction_output.json").unlink(missing_ok=True)

    _write_canned_response(dest, present=True, evidence_for_name=evidence_for_name)
    cfg = _write_stub_config(dest)

    rc = extract_main(["--folder", str(dest), "--voter", "stub", "--voter-config", str(cfg)])
    assert rc == 0, f"stub extractor failed for {src.name}"
    return dest


def _collect_evidence_ids(packet: dict) -> set[str]:
    ids: set[str] = set()
    for page in packet.get("pages", []) or []:
        for block in page.get("blocks", []) or []:
            if isinstance(block.get("block_id"), str):
                ids.add(block["block_id"])
        for line in page.get("raw_ocr_lines", []) or []:
            if isinstance(line.get("line_id"), str):
                ids.add(line["line_id"])
    return ids


def _iter_evidence(artifact: dict):
    vc = artifact["vendor_candidate"]
    yield from vc["company_name"]["evidence"]
    for v in vc["address"].values():
        yield from v["evidence"]
    for v in vc["tax_ids"].values():
        yield from v["evidence"]
    for key in ("website", "phone", "email"):
        yield from vc[key]["evidence"]
    hf = artifact["invoice_header_fields"]
    for key in ("invoice_number", "invoice_date"):
        yield from hf[key]["evidence"]
    yield from hf["total_amount"]["evidence"]


def test_all_20_docs_schema_valid(tmp_path: Path) -> None:
    """SC-001 on the stub path: every preprocess_output.json in the corpus
    produces a schema-valid edge_extraction_output.json."""

    folders = _corpus_folders()
    if not folders:
        pytest.skip("stage1 vendor-identity corpus is empty (authored by separate workstream)")

    for src in folders:
        dest = _run_stub(tmp_path, src, evidence_for_name=True)
        outcome = validate_artifact(
            dest / "edge_extraction_output.json",
            ArtifactName.EDGE_EXTRACTION_OUTPUT,
        )
        assert outcome.passed, (
            f"{src.name}: {[(v.field_path, v.violation_code) for v in outcome.violations]}"
        )


def test_missing_name_invariant_100pct(tmp_path: Path) -> None:
    """SC-002 on the stub path: with a stub that claims `present=true, evidence=[]`,
    every missing-name folder's artifact must show `present=false, inferred=true`."""

    folders = _missing_name_folders()
    if not folders:
        pytest.skip("no inv_*_missing_name/ folders in the corpus yet")

    for src in folders:
        dest = _run_stub(tmp_path, src, evidence_for_name=False)
        payload = json.loads((dest / "edge_extraction_output.json").read_text(encoding="utf-8"))
        cn = payload["vendor_candidate"]["company_name"]
        assert cn["present"] is False, f"{src.name}: present should be False"
        assert cn["inferred"] is True, f"{src.name}: inferred should be True"


def test_evidence_resolves_100pct(tmp_path: Path) -> None:
    """SC-003 on the stub path: every evidence ID in the output resolves against
    the corresponding preprocess packet."""

    folders = _corpus_folders()
    if not folders:
        pytest.skip("stage1 vendor-identity corpus is empty")

    for src in folders:
        dest = _run_stub(tmp_path, src, evidence_for_name=True)
        packet = json.loads((dest / "preprocess_output.json").read_text(encoding="utf-8"))
        artifact = json.loads((dest / "edge_extraction_output.json").read_text(encoding="utf-8"))

        known = _collect_evidence_ids(packet)
        for eid in _iter_evidence(artifact):
            assert _EVIDENCE_ID.match(eid), f"{src.name}: malformed id survived: {eid!r}"
            assert eid in known, f"{src.name}: unresolved evidence id in output: {eid}"
