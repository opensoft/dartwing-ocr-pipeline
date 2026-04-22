"""T006: FOLDER_SOURCE_PDF_UNREADABLE contract tests.

Covers the five cases enumerated in
`specs/006-corpus-labeling/contracts/validator-delta.md`.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from ledgerlinc_ocr.validator import validate_folder
from ledgerlinc_ocr.validator.report import Severity, ViolationCode


def _write_minimal_pdf(path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    path.write_bytes(buf.getvalue())


def _make_folder(tmp_path: Path, name: str = "inv_001_easy") -> Path:
    folder = tmp_path / name
    folder.mkdir()
    # Schema-conforming expected.json so the folder has the required unconditional files.
    (folder / "expected.json").write_text(
        f"""{{
  "contract_set_version": "1.0.0",
  "document_id": "{name}",
  "difficulty": "{name.rsplit('_', 1)[-1]}",
  "challenge_tags": ["explicit_company_name"],
  "expected_review": {{
    "manual_review_required": false,
    "review_reason": null
  }},
  "expected_vendor_candidate": {{
    "company_name": {{
      "value": "Acme Inc.",
      "present": true,
      "inferred": false
    }},
    "address": {{
      "street_1": null,
      "street_2": null,
      "city": null,
      "state": null,
      "postal_code": null,
      "country": null
    }},
    "tax_ids": {{
      "ein": null,
      "state_tax_id": null,
      "vat_id": null,
      "other_tax_id": null
    }},
    "website": null,
    "phone": null,
    "email": null
  }}
}}
""",
        encoding="utf-8",
    )
    return folder


def _pdf_unreadable_findings(outcome) -> list:
    return [
        v for v in outcome.violations
        if v.violation_code == ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE
    ]


def test_valid_minimal_pdf_passes(tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    _write_minimal_pdf(folder / "source.pdf")

    outcome = validate_folder(folder)

    assert _pdf_unreadable_findings(outcome) == []


def test_missing_source_pdf_does_not_emit_unreadable(tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    # Intentionally do not create source.pdf.

    outcome = validate_folder(folder)

    missing = [
        v for v in outcome.violations
        if v.violation_code == ViolationCode.FOLDER_MISSING_REQUIRED_FILE
        and "source.pdf" in v.field_path
    ]
    assert missing, "expected FOLDER_MISSING_REQUIRED_FILE for source.pdf"
    assert _pdf_unreadable_findings(outcome) == [], (
        "FOLDER_SOURCE_PDF_UNREADABLE must not duplicate FOLDER_MISSING_REQUIRED_FILE "
        "when source.pdf is absent"
    )


def test_zero_byte_source_pdf_emits_unreadable(tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    (folder / "source.pdf").write_bytes(b"")

    outcome = validate_folder(folder)

    findings = _pdf_unreadable_findings(outcome)
    assert len(findings) == 1
    v = findings[0]
    assert v.severity == Severity.ERROR
    assert v.field_path == "/source.pdf"
    assert v.expected == "FR-003 readable source.pdf"
    assert "0 bytes" in v.reason or "empty" in v.reason.lower()


def test_text_file_renamed_pdf_emits_unreadable(tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    (folder / "source.pdf").write_text(
        "this is plain text, not a PDF\n", encoding="utf-8"
    )

    outcome = validate_folder(folder)

    findings = _pdf_unreadable_findings(outcome)
    assert len(findings) == 1
    v = findings[0]
    assert v.severity == Severity.ERROR
    assert v.field_path == "/source.pdf"
    assert v.expected == "FR-003 readable source.pdf"


def test_truncated_pdf_emits_unreadable(tmp_path: Path) -> None:
    folder = _make_folder(tmp_path)
    buf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buf)
    full = buf.getvalue()
    # Keep the %PDF-<ver> header but drop the xref+trailer+%%EOF by truncating
    # the last ~quarter of the bytes.
    truncated = full[: max(64, len(full) // 2)]
    (folder / "source.pdf").write_bytes(truncated)

    outcome = validate_folder(folder)

    findings = _pdf_unreadable_findings(outcome)
    assert len(findings) == 1
    v = findings[0]
    assert v.severity == Severity.ERROR
    assert v.field_path == "/source.pdf"
    assert v.expected == "FR-003 readable source.pdf"
