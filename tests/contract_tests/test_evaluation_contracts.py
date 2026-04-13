"""T060: evaluation_document + evaluation_run_summary contracts."""
from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.validator import ArtifactName, validate_artifact
from ledgerlinc_ocr.validator.report import ViolationCode


def test_good_evaluation_document_passes(good_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        good_fixtures_root / "evaluation_document.json",
        ArtifactName.EVALUATION_DOCUMENT,
    )
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]


def test_good_evaluation_run_summary_passes(good_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        good_fixtures_root / "evaluation_run_summary.json",
        ArtifactName.EVALUATION_RUN_SUMMARY,
    )
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]


def test_single_voter_baseline_consensus_metrics_ok(
    good_fixtures_root: Path,
) -> None:
    # The good fixture omits the ensemble-only fields; it must still pass.
    outcome = validate_artifact(
        good_fixtures_root / "evaluation_run_summary.json",
        ArtifactName.EVALUATION_RUN_SUMMARY,
    )
    assert outcome.passed


def test_invalid_result_vocabulary_rejected(bad_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        bad_fixtures_root / "evaluation_document_invalid_result.json",
        ArtifactName.EVALUATION_DOCUMENT,
    )
    assert not outcome.passed
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.SCHEMA_ENUM_VIOLATION in codes


def test_document_count_mismatch_rejected(bad_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        bad_fixtures_root / "evaluation_run_summary_document_count_mismatch.json",
        ArtifactName.EVALUATION_RUN_SUMMARY,
    )
    assert not outcome.passed
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.DOCUMENT_COUNT_MISMATCH in codes
