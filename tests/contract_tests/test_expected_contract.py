"""T046: `expected` artifact contract — good + bad + missing-name triad."""
from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.validator import ArtifactName, validate_artifact
from ledgerlinc_ocr.validator.report import ViolationCode


def test_explicit_easy_passes(good_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        good_fixtures_root / "expected_explicit_easy.json", ArtifactName.EXPECTED
    )
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]


def test_missing_name_passes_when_triad_consistent(
    good_fixtures_root: Path,
) -> None:
    outcome = validate_artifact(
        good_fixtures_root / "expected_missing_name.json", ArtifactName.EXPECTED
    )
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]


def test_expected_rejects_confidence_field(bad_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        bad_fixtures_root / "expected_contains_confidence.json",
        ArtifactName.EXPECTED,
    )
    assert not outcome.passed
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.EXPECTED_HAS_PREDICTIONS in codes


def test_expected_rejects_unknown_challenge_tag(bad_fixtures_root: Path) -> None:
    outcome = validate_artifact(
        bad_fixtures_root / "expected_unknown_challenge_tag.json",
        ArtifactName.EXPECTED,
    )
    assert not outcome.passed
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.CHALLENGE_TAG_UNKNOWN in codes


def test_missing_name_violation_when_triad_broken(
    good_fixtures_root: Path, tmp_path: Path
) -> None:
    import json
    doc = json.loads(
        (good_fixtures_root / "expected_missing_name.json").read_text(encoding="utf-8")
    )
    # Flip manual_review_required to false — triad broken
    doc["expected_review"]["manual_review_required"] = False
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    outcome = validate_artifact(path, ArtifactName.EXPECTED)
    assert not outcome.passed
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.MISSING_NAME_TRIAD_VIOLATION in codes
