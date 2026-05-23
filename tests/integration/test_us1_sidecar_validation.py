"""T018 (US1): acceptance tests AS1-AS5 for the sidecar validator + CLI surface.

AS1: well-formed sidecar in a scored folder accepted.
AS2: mismatched ``document_id`` rejected with a named-mismatch error.
AS3: malformed row (duplicate row_id) rejected with a row-identifying error.
AS4: folder with no sidecar still validates under the existing
     ``expected.json`` contract (FR-005).
AS5: ``expected.json`` shape unchanged — fixture written with the original
     vendor-identity-only shape still validates (FR-006 / MI-23).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dartwing_ocr.validator.semantic_table_truth import (
    SidecarErrorKind,
    validate_sidecar,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GOOD_FIXTURE_FOLDER = (
    REPO_ROOT
    / "tests"
    / "contract_tests"
    / "fixtures"
    / "good"
    / "folders"
    / "inv_001_easy"
)


def _good_sidecar(folder_name: str) -> dict:
    return {
        "document_id": folder_name,
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["widget"],
                "unit_price": "21.00",
            },
            {
                "row_id": "row-2",
                "required_row_text_tokens": ["bolt"],
                "amount": "420.00",
            },
        ],
    }


def _copy_good_folder(target_root: Path, folder_name: str = "inv_001_easy") -> Path:
    target = target_root / folder_name
    shutil.copytree(GOOD_FIXTURE_FOLDER, target)
    if folder_name != "inv_001_easy":
        # Rewrite expected.json document_id to match the new folder name.
        exp = target / "expected.json"
        data = json.loads(exp.read_text(encoding="utf-8"))
        data["document_id"] = folder_name
        # Preserve difficulty match.
        if folder_name.endswith("_hard"):
            data["difficulty"] = "hard"
        elif folder_name.endswith("_medium"):
            data["difficulty"] = "medium"
        else:
            data["difficulty"] = "easy"
        exp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return target


def _write_sidecar(folder: Path, payload: dict) -> Path:
    p = folder / "semantic_table_truth.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# AS1: well-formed sidecar accepted.
# ---------------------------------------------------------------------------


def test_as1_well_formed_sidecar_accepted(tmp_path: Path) -> None:
    folder = _copy_good_folder(tmp_path, "inv_001_easy")
    _write_sidecar(folder, _good_sidecar("inv_001_easy"))

    result = validate_sidecar(folder)

    assert result.passed is True
    assert result.errors == ()


# ---------------------------------------------------------------------------
# AS2: mismatched document_id rejected; CLI exit code 3.
# ---------------------------------------------------------------------------


def test_as2_mismatched_document_id_rejected_with_named_error(tmp_path: Path) -> None:
    folder = _copy_good_folder(tmp_path, "inv_001_easy")
    _write_sidecar(folder, _good_sidecar("inv_999_hard"))  # declared != folder

    result = validate_sidecar(folder)

    assert result.passed is False
    mismatches = [
        e for e in result.errors if e.kind == SidecarErrorKind.DOCUMENT_ID_MISMATCH
    ]
    assert mismatches
    msg = mismatches[0].message
    assert "inv_999_hard" in msg
    assert "inv_001_easy" in msg


def test_as2_cli_validate_semantic_truth_exit_code_3(tmp_path: Path) -> None:
    folder = _copy_good_folder(tmp_path, "inv_001_easy")
    _write_sidecar(folder, _good_sidecar("inv_999_hard"))

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dartwing_ocr.validator",
            "validate",
            "semantic-truth",
            str(folder),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert completed.returncode == 3, completed.stderr


# ---------------------------------------------------------------------------
# AS3: duplicate row_id rejected; CLI exit code 4.
# ---------------------------------------------------------------------------


def test_as3_duplicate_row_id_rejected_with_row_identifying_error(
    tmp_path: Path,
) -> None:
    folder = _copy_good_folder(tmp_path, "inv_001_easy")
    sidecar = {
        "document_id": "inv_001_easy",
        "rows": [
            {"row_id": "row-1", "required_row_text_tokens": ["a"]},
            {"row_id": "row-1", "required_row_text_tokens": ["b"]},
        ],
    }
    _write_sidecar(folder, sidecar)

    result = validate_sidecar(folder)

    assert result.passed is False
    rows = [e for e in result.errors if e.kind == SidecarErrorKind.ROW_VIOLATION]
    assert rows
    assert any("row-1" in e.message for e in rows)


def test_as3_cli_validate_semantic_truth_exit_code_4(tmp_path: Path) -> None:
    folder = _copy_good_folder(tmp_path, "inv_001_easy")
    sidecar = {
        "document_id": "inv_001_easy",
        "rows": [
            {"row_id": "row-1", "required_row_text_tokens": ["a"]},
            {"row_id": "row-1", "required_row_text_tokens": ["b"]},
        ],
    }
    _write_sidecar(folder, sidecar)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dartwing_ocr.validator",
            "validate",
            "semantic-truth",
            str(folder),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO_ROOT / "src"), "PATH": "/usr/bin:/bin"},
    )
    assert completed.returncode == 4, completed.stderr


# ---------------------------------------------------------------------------
# AS4: folder with no sidecar still validates (FR-005 — no new requirement).
# ---------------------------------------------------------------------------


def test_as4_folder_without_sidecar_still_passes_folder_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = _copy_good_folder(tmp_path, "inv_001_easy")
    # No sidecar written.

    # The PDF-readability check is not in scope for this acceptance test.
    monkeypatch.setattr(
        "dartwing_ocr.validator.folder._check_source_pdf_readable",
        lambda _path, *, target: [],
    )

    from dartwing_ocr.validator import validate_folder

    outcome = validate_folder(folder)
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]


# ---------------------------------------------------------------------------
# AS5: expected.json shape unchanged — fixture written with the original
# vendor-identity-only shape still validates (FR-006 / MI-23).
# ---------------------------------------------------------------------------


def test_as5_expected_json_vendor_identity_shape_still_validates() -> None:
    """The fixture-stored expected.json should still pass artifact validation
    against the EXPECTED contract at v1.3.0 without any sidecar-related
    rejection — proves FR-006 / MI-23 (expected.json shape unchanged)."""
    from dartwing_ocr.validator.artifact import validate_artifact
    from dartwing_ocr.validator.report import ArtifactName

    expected_path = GOOD_FIXTURE_FOLDER / "expected.json"
    outcome = validate_artifact(
        expected_path, ArtifactName.EXPECTED, version="1.3.0"
    )
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]
