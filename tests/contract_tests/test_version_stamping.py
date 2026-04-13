"""T015: contract_set_version / pipeline_version / policy_version stamping.

Parametrized over every applicable artifact type. Uses minimal inline JSON
documents rather than the full good fixtures — those land in US1/US2/US3 and
this file intentionally does not depend on them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.validator import ValidationOutcome, validate_artifact
from ledgerlinc_ocr.validator.report import ArtifactName, ViolationCode

PIPELINE_ARTIFACTS = [
    ArtifactName.PREPROCESS_OUTPUT,
    ArtifactName.EDGE_EXTRACTION_OUTPUT,
    ArtifactName.ROUTING_DECISION,
    ArtifactName.FINAL_STRUCTURED_PAYLOAD,
]
NON_PIPELINE_ARTIFACTS = [
    ArtifactName.EXPECTED,
    ArtifactName.EVALUATION_DOCUMENT,
    ArtifactName.EVALUATION_RUN_SUMMARY,
]
ALL_ARTIFACTS = PIPELINE_ARTIFACTS + NON_PIPELINE_ARTIFACTS


def _write(tmp: Path, doc: dict) -> Path:
    p = tmp / "artifact.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _has_code(outcome: ValidationOutcome, code: str) -> bool:
    return any(v.violation_code == code for v in outcome.violations)


@pytest.mark.parametrize("artifact", ALL_ARTIFACTS)
def test_missing_contract_set_version(tmp_path: Path, artifact: ArtifactName) -> None:
    doc = {"document_id": "inv_001"}
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, artifact)
    assert _has_code(outcome, ViolationCode.CONTRACT_SET_VERSION_MISSING)
    assert outcome.passed is False


@pytest.mark.parametrize("artifact", ALL_ARTIFACTS)
def test_incompatible_major_version(tmp_path: Path, artifact: ArtifactName) -> None:
    doc = {"contract_set_version": "2.3.4", "document_id": "inv_001"}
    # pipeline versioned ones still need pipeline_version present to isolate this test
    if artifact in PIPELINE_ARTIFACTS:
        doc["pipeline_version"] = "stage1-edge-v0.1"
    if artifact is ArtifactName.ROUTING_DECISION:
        doc["policy_version"] = "stage1-routing-v0.1"
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, artifact)
    assert _has_code(outcome, ViolationCode.CONTRACT_SET_VERSION_INCOMPATIBLE)


@pytest.mark.parametrize("artifact", ALL_ARTIFACTS)
def test_compatible_minor_patch_version(
    tmp_path: Path, artifact: ArtifactName
) -> None:
    doc = {"contract_set_version": "1.2.3", "document_id": "inv_001"}
    if artifact in PIPELINE_ARTIFACTS:
        doc["pipeline_version"] = "stage1-edge-v0.1"
    if artifact is ArtifactName.ROUTING_DECISION:
        doc["policy_version"] = "stage1-routing-v0.1"
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, artifact)
    assert not _has_code(outcome, ViolationCode.CONTRACT_SET_VERSION_INCOMPATIBLE)
    assert not _has_code(outcome, ViolationCode.CONTRACT_SET_VERSION_MISSING)


@pytest.mark.parametrize("artifact", PIPELINE_ARTIFACTS)
def test_missing_pipeline_version_on_pipeline_artifacts(
    tmp_path: Path, artifact: ArtifactName
) -> None:
    doc = {"contract_set_version": "1.0.0", "document_id": "inv_001"}
    if artifact is ArtifactName.ROUTING_DECISION:
        doc["policy_version"] = "stage1-routing-v0.1"
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, artifact)
    assert _has_code(outcome, ViolationCode.PIPELINE_VERSION_MISSING)


def test_missing_policy_version_on_routing_decision(tmp_path: Path) -> None:
    doc = {
        "contract_set_version": "1.0.0",
        "document_id": "inv_001",
        "pipeline_version": "stage1-edge-v0.1",
    }
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, ArtifactName.ROUTING_DECISION)
    assert _has_code(outcome, ViolationCode.POLICY_VERSION_MISSING)


@pytest.mark.parametrize("artifact", NON_PIPELINE_ARTIFACTS)
def test_non_pipeline_artifacts_do_not_require_pipeline_version(
    tmp_path: Path, artifact: ArtifactName
) -> None:
    doc = {"contract_set_version": "1.0.0", "document_id": "inv_001"}
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, artifact)
    assert not _has_code(outcome, ViolationCode.PIPELINE_VERSION_MISSING)
    assert not _has_code(outcome, ViolationCode.POLICY_VERSION_MISSING)


@pytest.mark.parametrize(
    "artifact",
    [
        a
        for a in PIPELINE_ARTIFACTS + NON_PIPELINE_ARTIFACTS
        if a is not ArtifactName.ROUTING_DECISION
    ],
)
def test_policy_version_not_required_outside_routing_decision(
    tmp_path: Path, artifact: ArtifactName
) -> None:
    doc = {"contract_set_version": "1.0.0", "document_id": "inv_001"}
    if artifact in PIPELINE_ARTIFACTS:
        doc["pipeline_version"] = "stage1-edge-v0.1"
    path = _write(tmp_path, doc)
    outcome = validate_artifact(path, artifact)
    assert not _has_code(outcome, ViolationCode.POLICY_VERSION_MISSING)
