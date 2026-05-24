"""T045 (US3): backward-compat read path tests covering FR-019 / SC-008 / Q43.

Three scenarios pinned by Phase 5 task spec:

- (a) a pre-feature ``evaluation_document.json`` (no ``semantic_table_quality``,
  no ``semantic_table_quality_passed``) loaded through the backward-compat
  read path is accepted without raising.
- (b) the reader returns ``semantic_table_quality_passed = None`` (Python
  ``None`` ⇄ JSON ``null``) for the absent field (Q43 / MI-24).
- (c) a pre-feature ``evaluation_run_summary.json`` (no
  ``semantic_table_quality_metrics``, no ``semantic_document_statuses``)
  still validates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from dartwing_ocr.contract_versions import (
    ACTIVE_CONTRACT_SET_VERSION,
    PREVIOUS_CONTRACT_SET_VERSION,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_2_DOC_SCHEMA = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.2.0"
    / "evaluation_document.schema.json"
)
V1_3_DOC_SCHEMA = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.3.0"
    / "evaluation_document.schema.json"
)
V1_2_SUMMARY_SCHEMA = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.2.0"
    / "evaluation_run_summary.schema.json"
)
V1_3_SUMMARY_SCHEMA = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.3.0"
    / "evaluation_run_summary.schema.json"
)


@pytest.fixture(scope="module")
def doc_validator_v1_3() -> Draft202012Validator:
    return Draft202012Validator(json.loads(V1_3_DOC_SCHEMA.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def summary_validator_v1_3() -> Draft202012Validator:
    return Draft202012Validator(json.loads(V1_3_SUMMARY_SCHEMA.read_text(encoding="utf-8")))


def _pre_feature_eval_doc() -> dict:
    """A pre-feature evaluation_document.json — vendor-identity only, no
    semantic fields. Mirrors the v1.2.0 shape exactly."""
    return {
        "contract_set_version": "1.2.0",
        "document_id": "inv_001_hard",
        "difficulty": "hard",
        "challenge_tags": [],
        "comparison_summary": {
            "applicable_field_count": 1,
            "matched_field_count": 1,
            "mismatched_field_count": 0,
            "missing_prediction_count": 0,
            "unexpected_prediction_count": 0,
            "field_accuracy": 1.0,
        },
        "document_pass_fail": {
            "vendor_identity_passed": True,
            "review_routing_passed": True,
            "overall_passed": True,
        },
        "field_results": {},
        "notes": [],
    }


def _pre_feature_run_summary() -> dict:
    """A pre-feature evaluation_run_summary.json — no semantic keys.

    Thin wrapper around the shared helper (deduped per Sonar duplication
    finding on PR #47 2026-05-23).
    """
    from helpers.evaluation_artifacts import build_pre_feature_run_summary
    return build_pre_feature_run_summary()


# ---------------------------------------------------------------------------
# (a) Pre-feature evaluation_document.json validates under v1.3.0 schema
# ---------------------------------------------------------------------------


def test_a_pre_feature_eval_doc_validates_under_v1_3(
    doc_validator_v1_3: Draft202012Validator,
) -> None:
    """FR-019 / SC-008: a pre-1.3.0 evaluation_document.json with no
    semantic fields MUST schema-validate under the v1.3.0 schema. Both
    new fields are optional in the v1.3.0 schema."""
    doc = _pre_feature_eval_doc()
    errors = list(doc_validator_v1_3.iter_errors(doc))
    assert errors == [], f"pre-feature eval doc must validate: {errors}"


def test_a_pre_feature_eval_doc_also_validates_under_v1_2(
    doc_validator_v1_3: Draft202012Validator,
) -> None:
    """Sanity check: the same document also validates under the retained
    v1.2.0 schema (the read-tolerant loader uses PREVIOUS_CONTRACT_SET_VERSION
    per R-022.9)."""
    v1_2_schema = json.loads(V1_2_DOC_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(v1_2_schema)
    doc = _pre_feature_eval_doc()
    errors = list(validator.iter_errors(doc))
    assert errors == [], f"pre-feature eval doc must validate under v1.2.0: {errors}"


# ---------------------------------------------------------------------------
# (b) Reader returns semantic_table_quality_passed=None for absent field
# ---------------------------------------------------------------------------


def test_b_reader_interprets_absent_semantic_passed_as_none() -> None:
    """Q43 / MI-24: when reading a pre-feature evaluation_document.json
    that lacks document_pass_fail.semantic_table_quality_passed, the reader
    MUST interpret the absent field as Python None (= JSON null).

    The reader path lives at ``dartwing_ocr.validator.artifact`` (or the
    equivalent reader module per T053). Here we exercise the documented
    interpretation directly so the test is decoupled from any single
    call-site that might be added later.
    """
    from dartwing_ocr.validator.artifact import read_semantic_table_quality_passed

    doc = _pre_feature_eval_doc()
    assert "semantic_table_quality_passed" not in doc["document_pass_fail"]
    assert read_semantic_table_quality_passed(doc) is None


def test_b_reader_returns_explicit_value_when_present() -> None:
    """When the field IS present, the reader returns its value verbatim."""
    from dartwing_ocr.validator.artifact import read_semantic_table_quality_passed

    doc = _pre_feature_eval_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = True
    assert read_semantic_table_quality_passed(doc) is True

    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    assert read_semantic_table_quality_passed(doc) is False

    doc["document_pass_fail"]["semantic_table_quality_passed"] = None
    assert read_semantic_table_quality_passed(doc) is None


# ---------------------------------------------------------------------------
# (c) Pre-feature evaluation_run_summary.json still validates under v1.3.0
# ---------------------------------------------------------------------------


def test_c_pre_feature_run_summary_validates_under_v1_3(
    summary_validator_v1_3: Draft202012Validator,
) -> None:
    """FR-019 / SC-008: a pre-1.3.0 evaluation_run_summary.json with no
    semantic_table_quality_metrics and no semantic_document_statuses MUST
    schema-validate under the v1.3.0 schema."""
    doc = _pre_feature_run_summary()
    errors = list(summary_validator_v1_3.iter_errors(doc))
    assert errors == [], f"pre-feature run summary must validate: {errors}"


# ---------------------------------------------------------------------------
# Contract version constant sanity (R-022.9): both PREVIOUS and ACTIVE
# constants are exposed and the previous version is still loadable
# ---------------------------------------------------------------------------


def test_previous_contract_set_version_constant_retained() -> None:
    """R-022.9: PREVIOUS_CONTRACT_SET_VERSION = '1.2.0' is retained so
    backward-compat readers can still validate pre-1.3.0 artifacts."""
    assert PREVIOUS_CONTRACT_SET_VERSION == "1.2.0"
    assert ACTIVE_CONTRACT_SET_VERSION == "1.3.0"


def test_previous_contract_set_is_still_loadable() -> None:
    """The v1.2.0 contract set MUST still load via load_contract_set("1.2.0")."""
    from dartwing_ocr.validator.loader import load_contract_set

    cs = load_contract_set(PREVIOUS_CONTRACT_SET_VERSION)
    assert cs.version == "1.2.0"


# ---------------------------------------------------------------------------
# Codex P1 PR #47 review fix (2026-05-23) — writer respects pinned version
# ---------------------------------------------------------------------------


def _build_evaluation_for_version_test(
    *,
    contract_set_version: str,
    semantic_status: str,
    folder_path: Path,
):
    """Build a minimal DocumentEvaluation for the version-guard tests.

    Extracted as a helper to reduce duplication between the v1.2.0 and
    v1.3.0 writer-gating tests (Sonar python:S4144 — duplicate code)
    and to scope the noisy import block to one place.
    """
    from dartwing_ocr.evaluator.compare import FieldResult
    from dartwing_ocr.evaluator.document import DocumentEvaluation
    from dartwing_ocr.evaluator.gates import DocumentPassFail
    from dartwing_ocr.evaluator.scoring import (
        ComparisonSummary,
        ResultLabel,
        SCORED_FIELDS,
    )
    from dartwing_ocr.evaluator.semantic_quality_report import (
        SemanticQualityResult,
        SupportingEvidence,
    )

    field_results = tuple(
        FieldResult(
            field_name=name,
            expected=None,
            actual=None,
            result=ResultLabel.NOT_APPLICABLE,
        )
        for name in SCORED_FIELDS
    )
    return DocumentEvaluation(
        contract_set_version=contract_set_version,
        document_id="inv_001_easy",
        difficulty="easy",
        challenge_tags=(),
        comparison_summary=ComparisonSummary(
            applicable_field_count=0,
            matched_field_count=0,
            mismatched_field_count=0,
            missing_prediction_count=0,
            unexpected_prediction_count=0,
            field_accuracy=0.0,
        ),
        document_pass_fail=DocumentPassFail(
            vendor_identity_passed=False,
            review_routing_passed=False,
            overall_passed=False,
        ),
        field_results=field_results,
        notes=(),
        document_score=1.0,
        folder_path=folder_path,
        semantic_quality_result=SemanticQualityResult(
            status=semantic_status,
            failed_checks=[],
            row_reasons=None,
            supporting_evidence=SupportingEvidence(
                body_confidence_mean=0.9,
                body_confidence_min=0.9,
                body_line_count=1,
                body_token_count=1,
                header_band_excluded=False,
            ),
            cause=None,
            cause_detail=None,
        ),
    )


def test_writer_pinned_to_v1_2_omits_semantic_fields(tmp_path: Path) -> None:
    """Per Codex P1 on PR #47: writer with contract_set_version='1.2.0' must
    NOT emit semantic_table_quality / semantic_table_quality_passed.

    This preserves the v1.2.0 schema's byte-identity (MI-22) for callers
    that explicitly pin the older contract version. The new fields are
    additive in v1.3.0+ only; emitting them on a v1.2.0-pinned doc would
    cause the older schema validator to fail.

    Uses pytest's tmp_path fixture (NOT a hardcoded /tmp/... path) to
    satisfy Sonar python:S5443 — publicly-writable directory.
    """
    from dartwing_ocr.evaluator.document import supports_semantic_quality_fields

    # Sanity: helper says v1.2.0 does NOT support semantic fields.
    assert supports_semantic_quality_fields("1.2.0") is False
    assert supports_semantic_quality_fields("1.3.0") is True

    # Build a v1.2.0-pinned evaluation with a populated semantic result —
    # the writer should STILL skip the semantic keys.
    evaluation = _build_evaluation_for_version_test(
        contract_set_version="1.2.0",
        semantic_status="failed",
        folder_path=tmp_path / "inv_001_easy",
    )
    out = evaluation.to_persistable_dict()
    # v1.2.0 writer must NOT emit either semantic key.
    assert "semantic_table_quality" not in out, (
        "v1.2.0-pinned writer leaked semantic_table_quality"
    )
    assert "semantic_table_quality_passed" not in out["document_pass_fail"], (
        "v1.2.0-pinned writer leaked document_pass_fail.semantic_table_quality_passed"
    )
    # And the resulting doc MUST validate against the v1.2.0 schema.
    schema = json.loads(V1_2_DOC_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(out))
    assert not errors, f"v1.2.0-pinned output failed v1.2.0 schema: {errors}"


def test_writer_pinned_to_v1_3_emits_semantic_fields(tmp_path: Path) -> None:
    """Per Codex P1 PR #47: v1.3.0-pinned writer DOES emit semantic fields.

    Symmetric check that the version-guard helper isn't accidentally
    suppressing emission for the current pinned version.

    Uses pytest's tmp_path fixture (NOT a hardcoded /tmp/... path) to
    satisfy Sonar python:S5443 — publicly-writable directory.
    """
    evaluation = _build_evaluation_for_version_test(
        contract_set_version="1.3.0",
        semantic_status="passed",
        folder_path=tmp_path / "inv_001_easy",
    )
    out = evaluation.to_persistable_dict()
    assert "semantic_table_quality" in out
    assert "semantic_table_quality_passed" in out["document_pass_fail"]
    assert out["document_pass_fail"]["semantic_table_quality_passed"] is True
