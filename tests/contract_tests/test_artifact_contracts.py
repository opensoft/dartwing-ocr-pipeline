"""T026: artifact-level contracts for the four pipeline artifacts.

Exercises good fixtures (must pass) and bad fixtures (must fail with the
expected violation_code).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlinc_ocr.validator import ArtifactName, validate_artifact
from ledgerlinc_ocr.validator.report import ViolationCode


PIPELINE_GOODS = [
    ("preprocess_output", ArtifactName.PREPROCESS_OUTPUT),
    ("edge_extraction_output", ArtifactName.EDGE_EXTRACTION_OUTPUT),
    ("routing_decision", ArtifactName.ROUTING_DECISION),
    ("final_structured_payload", ArtifactName.FINAL_STRUCTURED_PAYLOAD),
]


@pytest.mark.parametrize("stem,contract", PIPELINE_GOODS)
def test_good_fixture_passes(
    good_fixtures_root: Path, stem: str, contract: ArtifactName
) -> None:
    path = good_fixtures_root / f"{stem}.json"
    outcome = validate_artifact(path, contract)
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]
    assert outcome.counts.error == 0


@pytest.mark.parametrize(
    "bad_stem,contract,expected_code",
    [
        ("empty_string_for_null", ArtifactName.EDGE_EXTRACTION_OUTPUT, ViolationCode.NULL_VS_EMPTY_STRING),
        ("missing_vote_metadata", ArtifactName.EDGE_EXTRACTION_OUTPUT, ViolationCode.VOTE_METADATA_MISSING),
        ("tax_id_invalid_type", ArtifactName.EDGE_EXTRACTION_OUTPUT, ViolationCode.TAX_ID_TYPE_INVALID),
        ("review_reason_null_when_required", ArtifactName.ROUTING_DECISION, ViolationCode.REVIEW_REASON_NULL_WHEN_REQUIRED),
        ("inferred_without_review_required", ArtifactName.FINAL_STRUCTURED_PAYLOAD, ViolationCode.MISSING_NAME_TRIAD_VIOLATION),
    ],
)
def test_bad_fixture_reports_expected_code(
    bad_fixtures_root: Path,
    bad_stem: str,
    contract: ArtifactName,
    expected_code: str,
) -> None:
    path = bad_fixtures_root / f"{bad_stem}.json"
    outcome = validate_artifact(path, contract)
    assert not outcome.passed
    codes = {v.violation_code for v in outcome.violations}
    assert expected_code in codes, (
        f"expected {expected_code} among {sorted(codes)} for {bad_stem}"
    )


def test_violation_entries_have_field_paths(bad_fixtures_root: Path) -> None:
    path = bad_fixtures_root / "tax_id_invalid_type.json"
    outcome = validate_artifact(path, ArtifactName.EDGE_EXTRACTION_OUTPUT)
    assert not outcome.passed
    # At least the TAX_ID_TYPE_INVALID entry must have a non-empty field_path.
    triggered = [
        v
        for v in outcome.violations
        if v.violation_code == ViolationCode.TAX_ID_TYPE_INVALID
    ]
    assert triggered, "expected a TAX_ID_TYPE_INVALID entry"
    assert all(v.field_path.startswith("/vendor_candidate/tax_ids") for v in triggered)


def test_empty_string_violation_names_the_offending_field(
    bad_fixtures_root: Path,
) -> None:
    path = bad_fixtures_root / "empty_string_for_null.json"
    outcome = validate_artifact(path, ArtifactName.EDGE_EXTRACTION_OUTPUT)
    triggered = [
        v
        for v in outcome.violations
        if v.violation_code == ViolationCode.NULL_VS_EMPTY_STRING
    ]
    assert triggered
    assert any(v.field_path == "/vendor_candidate/phone/value" for v in triggered)
