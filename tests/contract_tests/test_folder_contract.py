"""T047: folder-layout contract — required files, conditional notes.md, reserved names."""
from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.validator import validate_folder
from ledgerlinc_ocr.validator.report import Severity, ViolationCode


def test_good_folder_passes(good_fixtures_root: Path) -> None:
    folder = good_fixtures_root / "folders" / "inv_001_easy"
    outcome = validate_folder(folder)
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]
    assert outcome.counts.warning == 0


def test_missing_notes_on_hard_fails(bad_fixtures_root: Path) -> None:
    folder = bad_fixtures_root / "folders" / "inv_003_hard"
    outcome = validate_folder(folder)
    assert outcome.passed is False
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.FOLDER_MISSING_REQUIRED_FILE in codes
    # Must specifically name notes.md
    triad = [
        v for v in outcome.violations
        if v.violation_code == ViolationCode.FOLDER_MISSING_REQUIRED_FILE
        and "notes.md" in v.field_path
    ]
    assert triad


def test_missing_notes_on_easy_only_warns(bad_fixtures_root: Path) -> None:
    folder = bad_fixtures_root / "folders" / "inv_004_easy"
    outcome = validate_folder(folder)
    assert outcome.passed is True
    assert outcome.counts.error == 0
    assert outcome.counts.warning == 1
    assert outcome.warnings[0].violation_code == ViolationCode.FOLDER_NOTES_MISSING_SOFT
    assert outcome.warnings[0].severity == Severity.WARNING


def test_missing_source_pdf_fails(bad_fixtures_root: Path) -> None:
    folder = bad_fixtures_root / "folders" / "inv_005_easy"
    outcome = validate_folder(folder)
    assert outcome.passed is False
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.FOLDER_MISSING_REQUIRED_FILE in codes
    offenders = [
        v for v in outcome.violations
        if v.violation_code == ViolationCode.FOLDER_MISSING_REQUIRED_FILE
        and "source.pdf" in v.field_path
    ]
    assert offenders


def test_folder_name_invalid(bad_fixtures_root: Path) -> None:
    folder = bad_fixtures_root / "folders" / "invoice_001_easy"
    outcome = validate_folder(folder)
    assert outcome.passed is False
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.FOLDER_NAME_INVALID in codes


def test_reserved_filename_collision(bad_fixtures_root: Path) -> None:
    folder = bad_fixtures_root / "folders" / "inv_002_easy"
    outcome = validate_folder(folder)
    assert outcome.passed is False
    codes = {v.violation_code for v in outcome.violations}
    assert ViolationCode.FOLDER_RESERVED_FILENAME_COLLISION in codes
    offenders = [
        v for v in outcome.violations
        if v.violation_code == ViolationCode.FOLDER_RESERVED_FILENAME_COLLISION
    ]
    # Violation must name the offending file
    assert any("preprocess_output.json" in v.field_path for v in offenders)
