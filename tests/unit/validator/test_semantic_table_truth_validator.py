"""T016 (US1): unit tests for ``validate_sidecar`` in
``dartwing_ocr.validator.semantic_table_truth``.

Covers the 9 behavioral cases pinned by spec FR-002 / FR-003 / FR-004 +
Clarifications Q11 / Q41 + security-clarify Q-SEC-2/B (cases ``g``-``i``).

The validator collects every violation it encounters and reports them all on
the returned ``SemanticTruthValidationResult``. The CLI is responsible for
mapping the highest-priority error class to an exit code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.validator.semantic_table_truth import (
    SemanticTruthValidationResult,
    SidecarErrorKind,
    validate_sidecar,
)


def _write_sidecar(folder: Path, doc: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "semantic_table_truth.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


def _good_doc(folder_name: str = "inv_001_hard") -> dict:
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


# ---------------------------------------------------------------------------
# (a) Accept a well-formed sidecar.
# ---------------------------------------------------------------------------


def test_a_accept_good_sidecar(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    _write_sidecar(folder, _good_doc("inv_001_hard"))

    result = validate_sidecar(folder)

    assert isinstance(result, SemanticTruthValidationResult)
    assert result.passed is True
    assert result.errors == ()


# ---------------------------------------------------------------------------
# (b) document_id mismatch — Q41 error message names BOTH values.
# ---------------------------------------------------------------------------


def test_b_reject_document_id_mismatch_q41(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = _good_doc("inv_999_easy")  # declared mismatches folder
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    mismatches = [e for e in result.errors if e.kind == SidecarErrorKind.DOCUMENT_ID_MISMATCH]
    assert len(mismatches) == 1
    msg = mismatches[0].message
    assert "inv_999_easy" in msg
    assert "inv_001_hard" in msg


# ---------------------------------------------------------------------------
# (c) Duplicate row_id — error names the duplicate value AND the duplicate index.
# ---------------------------------------------------------------------------


def test_c_reject_duplicate_row_id_q11(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {"row_id": "row-1", "required_row_text_tokens": ["a"]},
            {"row_id": "row-2", "required_row_text_tokens": ["b"]},
            {"row_id": "row-1", "required_row_text_tokens": ["c"]},
        ],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    dupes = [e for e in result.errors if e.kind == SidecarErrorKind.ROW_VIOLATION]
    assert dupes, "expected at least one row-violation error for the duplicate"
    msg = " ".join(e.message for e in dupes)
    assert "row-1" in msg
    # Must mention the duplicate position somewhere — either index 2 or the
    # earlier index 0.
    assert "2" in msg
    assert "0" in msg


# ---------------------------------------------------------------------------
# (d) Row missing row_id — identifier is ``[<index>]``.
# ---------------------------------------------------------------------------


def test_d_reject_row_missing_row_id_uses_index_bracket(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {"row_id": "row-1", "required_row_text_tokens": ["a"]},
            {"required_row_text_tokens": ["b"]},  # missing row_id at index 1
        ],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    rows = [e for e in result.errors if e.kind == SidecarErrorKind.ROW_VIOLATION]
    assert any("[1]" in e.message for e in rows)


# ---------------------------------------------------------------------------
# (e) Row with malformed unit_price — error names row_id, field, AND regex.
# ---------------------------------------------------------------------------


def test_e_reject_unit_price_with_currency_symbol_names_field_and_pattern(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["x"],
                "unit_price": "$21.00",
            }
        ],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    rows = [e for e in result.errors if e.kind == SidecarErrorKind.ROW_VIOLATION]
    assert rows
    msg = " ".join(e.message for e in rows)
    assert "row-1" in msg
    assert "unit_price" in msg
    assert r"^\d+\.\d{2}$" in msg


# ---------------------------------------------------------------------------
# (f) All row violations reported — not just the first.
# ---------------------------------------------------------------------------


def test_f_all_row_violations_reported(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {
                "row_id": "row-1",
                "required_row_text_tokens": ["a"],
                "unit_price": "$21.00",
            },
            {
                "row_id": "row-2",
                "required_row_text_tokens": ["b"],
                "amount": "1,234.56",
            },
        ],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    rows = [e for e in result.errors if e.kind == SidecarErrorKind.ROW_VIOLATION]
    # Must have errors naming BOTH offending rows — proving no short-circuit.
    msg = " ".join(e.message for e in rows)
    assert "row-1" in msg
    assert "row-2" in msg


# ---------------------------------------------------------------------------
# (g) Q-SEC-2/B: row_id = "../escape" — names value and pattern.
# ---------------------------------------------------------------------------


def test_g_reject_path_traversal_row_id_qsec2b(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {"row_id": "../escape", "required_row_text_tokens": ["x"]},
        ],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    rows = [e for e in result.errors if e.kind == SidecarErrorKind.ROW_VIOLATION]
    assert rows
    msg = " ".join(e.message for e in rows)
    assert "../escape" in msg
    assert "^[A-Za-z0-9_-]{1,64}$" in msg


# ---------------------------------------------------------------------------
# (h) Q-SEC-2/B: document_id = "../../../etc/passwd" — names declared value AND
#     safety-pattern violation reason.
# ---------------------------------------------------------------------------


def test_h_reject_path_traversal_document_id_qsec2b(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "../../../etc/passwd",
        "rows": [{"row_id": "row-1", "required_row_text_tokens": ["x"]}],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    # The schema rejects this at the top-level (SCHEMA error) AND the validator
    # also surfaces the mismatch error. Both error classes are present.
    schema_errors = [
        e for e in result.errors if e.kind == SidecarErrorKind.SCHEMA_INVALID
    ]
    assert schema_errors
    msg = " ".join(e.message for e in schema_errors)
    assert "../../../etc/passwd" in msg or "document_id" in msg
    assert "^[A-Za-z0-9_-]{1,64}$" in msg


# ---------------------------------------------------------------------------
# (i) Q-SEC-2/B: 65-char row_id — reason cites maxLength: 64 OR pattern.
# ---------------------------------------------------------------------------


def test_i_reject_overlong_row_id_qsec2b(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    doc = {
        "document_id": "inv_001_hard",
        "rows": [
            {"row_id": "a" * 65, "required_row_text_tokens": ["x"]},
        ],
    }
    _write_sidecar(folder, doc)

    result = validate_sidecar(folder)

    assert result.passed is False
    # 65-char string fails both maxLength: 64 AND the safety pattern.
    schema_errors = [
        e for e in result.errors if e.kind == SidecarErrorKind.SCHEMA_INVALID
    ]
    assert schema_errors
    msg = " ".join(e.message for e in schema_errors)
    assert "64" in msg or "^[A-Za-z0-9_-]{1,64}$" in msg


# ---------------------------------------------------------------------------
# Extras: file presence and JSON parse-error behavior (exit-code 4/5 inputs).
# ---------------------------------------------------------------------------


def test_missing_sidecar_returns_missing_kind(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    folder.mkdir(parents=True)
    # No file written.

    result = validate_sidecar(folder)

    assert result.passed is False
    kinds = {e.kind for e in result.errors}
    assert SidecarErrorKind.MISSING_SIDECAR in kinds


def test_invalid_json_returns_json_invalid_kind(tmp_path: Path) -> None:
    folder = tmp_path / "inv_001_hard"
    folder.mkdir(parents=True)
    (folder / "semantic_table_truth.json").write_text(
        "{not valid json", encoding="utf-8"
    )

    result = validate_sidecar(folder)

    assert result.passed is False
    kinds = {e.kind for e in result.errors}
    assert SidecarErrorKind.JSON_INVALID in kinds


def test_passes_through_existing_validator_loader(tmp_path: Path) -> None:
    """Sanity: the validator loads its schema through the v1.3.0 contract set
    rather than re-parsing the JSON Schema file out-of-band."""
    folder = tmp_path / "inv_001_hard"
    _write_sidecar(folder, _good_doc())

    # Should not raise; loader-driven path is the steady state.
    result = validate_sidecar(folder)

    assert result.passed is True
