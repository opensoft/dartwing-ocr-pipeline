"""T014: report.ValidationOutcome round-trips through report.schema.json."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlinc_ocr.validator.report import (
    REPORT_VERSION,
    Severity,
    ValidationOutcome,
    Violation,
    ViolationCode,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORT_SCHEMA_PATH = (
    _REPO_ROOT
    / "specs"
    / "001-freeze-schemas-folder-contracts"
    / "contracts"
    / "report.schema.json"
)


@pytest.fixture(scope="module")
def report_schema() -> dict:
    return json.loads(_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema)


def test_passing_outcome_conforms(report_schema: dict) -> None:
    outcome = ValidationOutcome.build(
        contract_set_version_checked="1.0.0",
        target_summary="artifact:edge_extraction_output",
        findings=[],
    )
    errors = list(_validator(report_schema).iter_errors(outcome.to_json()))
    assert errors == []
    assert outcome.report_version == REPORT_VERSION


def test_failing_outcome_conforms(report_schema: dict) -> None:
    v = Violation(
        severity=Severity.ERROR,
        target="edge_extraction_output",
        field_path="/vendor_candidate/tax_ids/sales_tax",
        violation_code=ViolationCode.TAX_ID_TYPE_INVALID,
        reason="'sales_tax' is not an allowed tax-ID type.",
        expected="FR-012 tax_ids enum",
        source_file="/tmp/x.json",
    )
    outcome = ValidationOutcome.build(
        contract_set_version_checked="1.0.0",
        target_summary="artifact:edge_extraction_output",
        findings=[v],
    )
    errors = list(_validator(report_schema).iter_errors(outcome.to_json()))
    assert errors == []
    assert outcome.passed is False
    assert outcome.counts.error == 1
    assert outcome.counts.warning == 0


def test_warning_only_outcome_conforms(report_schema: dict) -> None:
    w = Violation(
        severity=Severity.WARNING,
        target="folder:tests/stage1_vendor_identity/inv_001_easy",
        field_path="",
        violation_code=ViolationCode.FOLDER_NOTES_MISSING_SOFT,
        reason="notes.md missing (easy/medium soft requirement).",
        expected="FR-029 notes.md conditional",
    )
    outcome = ValidationOutcome.build(
        contract_set_version_checked="1.0.0",
        target_summary="folder:tests/stage1_vendor_identity/inv_001_easy",
        findings=[w],
    )
    errors = list(_validator(report_schema).iter_errors(outcome.to_json()))
    assert errors == []
    assert outcome.passed is True
    assert outcome.counts.error == 0
    assert outcome.counts.warning == 1


def test_corpus_outcome_with_sub_reports_conforms(report_schema: dict) -> None:
    sub_a = ValidationOutcome.build(
        contract_set_version_checked="1.0.0",
        target_summary="folder:inv_001_easy",
        findings=[],
    )
    sub_b = ValidationOutcome.build(
        contract_set_version_checked="1.0.0",
        target_summary="folder:inv_002_hard",
        findings=[
            Violation(
                severity=Severity.ERROR,
                target="folder:inv_002_hard",
                violation_code=ViolationCode.FOLDER_MISSING_REQUIRED_FILE,
                reason="notes.md missing on hard document.",
                expected="FR-029 notes.md conditional",
            )
        ],
    )
    corpus = ValidationOutcome.build(
        contract_set_version_checked="1.0.0",
        target_summary="corpus:tests/stage1_vendor_identity",
        findings=[],
        sub_reports=[sub_a, sub_b],
    )
    errors = list(_validator(report_schema).iter_errors(corpus.to_json()))
    assert errors == []
    assert corpus.passed is False
    assert corpus.counts.error == 1
    assert corpus.counts.warning == 0
