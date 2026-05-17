"""T027: cross-artifact rules (provenance triad + evidence-reference)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from dartwing_ocr.validator.cross_artifact import (
    check_evidence_references,
    check_provenance_triad,
)
from dartwing_ocr.validator.report import ArtifactName, ViolationCode


def _load(root: Path, stem: str) -> dict:
    return json.loads((root / f"{stem}.json").read_text(encoding="utf-8"))


def _expected_doc(present: bool, inferred: bool, mrr: bool, reason: str | None) -> dict:
    return {
        "contract_set_version": "1.0.0",
        "document_id": "inv_001",
        "difficulty": "easy",
        "challenge_tags": [],
        "expected_review": {"manual_review_required": mrr, "review_reason": reason},
        "expected_vendor_candidate": {
            "company_name": {
                "value": "ACME Industrial Supply LLC",
                "present": present,
                "inferred": inferred,
            }
        },
    }


def test_provenance_triad_passes_on_consistent_quadruple(
    good_fixtures_root: Path,
) -> None:
    artifacts = {
        ArtifactName.EXPECTED: _expected_doc(True, False, False, None),
        ArtifactName.EDGE_EXTRACTION_OUTPUT: _load(good_fixtures_root, "edge_extraction_output"),
        ArtifactName.ROUTING_DECISION: _load(good_fixtures_root, "routing_decision"),
        ArtifactName.FINAL_STRUCTURED_PAYLOAD: _load(
            good_fixtures_root, "final_structured_payload"
        ),
    }
    findings = check_provenance_triad(
        artifacts, target="folder:test"
    )
    assert findings == [], [
        (v.violation_code, v.field_path, v.reason) for v in findings
    ]


def test_provenance_triad_flags_when_present_disagrees(
    good_fixtures_root: Path,
) -> None:
    artifacts = {
        ArtifactName.EXPECTED: _expected_doc(True, False, False, None),
        ArtifactName.EDGE_EXTRACTION_OUTPUT: _load(good_fixtures_root, "edge_extraction_output"),
        ArtifactName.FINAL_STRUCTURED_PAYLOAD: _load(
            good_fixtures_root, "final_structured_payload"
        ),
    }
    # Flip `present` on the final payload.
    fp = copy.deepcopy(artifacts[ArtifactName.FINAL_STRUCTURED_PAYLOAD])
    fp["vendor_candidate"]["company_name"]["present"] = False
    artifacts[ArtifactName.FINAL_STRUCTURED_PAYLOAD] = fp
    findings = check_provenance_triad(artifacts, target="folder:test")
    codes = {f.violation_code for f in findings}
    assert ViolationCode.PROVENANCE_TRIAD_INCONSISTENT in codes


def test_provenance_triad_flags_when_review_reason_disagrees(
    good_fixtures_root: Path,
) -> None:
    artifacts = {
        ArtifactName.EXPECTED: _expected_doc(True, False, False, None),
        ArtifactName.ROUTING_DECISION: _load(good_fixtures_root, "routing_decision"),
    }
    rd = copy.deepcopy(artifacts[ArtifactName.ROUTING_DECISION])
    rd["review_status"]["review_reason"] = "some_other_reason"
    artifacts[ArtifactName.ROUTING_DECISION] = rd
    findings = check_provenance_triad(artifacts, target="folder:test")
    codes = {f.violation_code for f in findings}
    assert ViolationCode.PROVENANCE_TRIAD_INCONSISTENT in codes


def test_evidence_references_resolve_on_good_pair(
    good_fixtures_root: Path,
) -> None:
    preprocess = _load(good_fixtures_root, "preprocess_output")
    extraction = _load(good_fixtures_root, "edge_extraction_output")
    findings = check_evidence_references(
        preprocess, extraction, target="folder:test"
    )
    assert findings == [], [
        (v.violation_code, v.field_path) for v in findings
    ]


def test_evidence_references_flags_unresolved_id(
    good_fixtures_root: Path, bad_fixtures_root: Path
) -> None:
    preprocess = _load(good_fixtures_root, "preprocess_output")
    extraction = _load(bad_fixtures_root, "evidence_reference_unresolved")
    findings = check_evidence_references(
        preprocess, extraction, target="folder:test"
    )
    codes = {f.violation_code for f in findings}
    assert ViolationCode.EVIDENCE_REFERENCE_UNRESOLVED in codes


def test_single_artifact_skips_cross_artifact_checks(
    good_fixtures_root: Path,
) -> None:
    only_extraction = {
        ArtifactName.EDGE_EXTRACTION_OUTPUT: _load(
            good_fixtures_root, "edge_extraction_output"
        )
    }
    findings = check_provenance_triad(only_extraction, target="folder:test")
    assert findings == []
