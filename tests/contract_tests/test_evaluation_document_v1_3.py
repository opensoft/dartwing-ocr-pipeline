"""T043 (US3): contract-level tests for the v1.3.0 ``evaluation_document.schema.json``.

Covers the nine acceptance/rejection cases (a)-(i) pinned by Phase 5 task
spec, including the post-fix F1/F2/F3/F5 vocabulary:

- ``failed_checks`` always present when the object is present (F5)
- ``row_reasons`` is a JSON OBJECT keyed by ``row_id`` (F1) with values
  ``{categories, reason}`` (F2) — NOT an array
- ``supporting_evidence.body_confidence_min`` always a ``number`` — never null (F3)
- ``cause`` enum tightly constrained to four closed-vocabulary values (Q31)
- ``semantic_table_quality_passed`` is ``boolean | null`` on
  ``document_pass_fail`` (MI-17 / Q20)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.3.0"
    / "evaluation_document.schema.json"
)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _is_valid(validator: Draft202012Validator, doc: dict) -> bool:
    return not list(validator.iter_errors(doc))


def _base_doc(**overrides) -> dict:
    """Build a minimal-valid v1.3.0 evaluation_document.json shell.

    Vendor-identity portion mirrors the v1.2.0 shape so any new test only
    needs to layer the v1.3.0 additive fields on top.
    """
    base = {
        "contract_set_version": "1.3.0",
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
    # Shallow merge — caller supplies overrides for the top-level keys it cares about.
    for k, v in overrides.items():
        base[k] = v
    return base


# ---------------------------------------------------------------------------
# (a) Report with no `semantic_table_quality` and `semantic_table_quality_passed: null`
# ---------------------------------------------------------------------------


def test_a_accepts_no_semantic_object_with_null_passed(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = None
    assert _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (b) Report with status=='passed', failed_checks=[], no row_reasons
# ---------------------------------------------------------------------------


def test_b_accepts_passed_status_empty_failed_checks_no_row_reasons(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = True
    doc["semantic_table_quality"] = {
        "status": "passed",
        "failed_checks": [],
        "supporting_evidence": {
            "body_confidence_mean": 0.97,
            "body_confidence_min": 0.94,
            "body_line_count": 24,
            "body_token_count": 187,
            "header_band_excluded": True,
        },
    }
    assert _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (c) Report with status=='failed', failed_checks non-empty, row_reasons object, evidence
# ---------------------------------------------------------------------------


def test_c_accepts_failed_status_with_row_reasons_object(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "failed",
        "failed_checks": [
            {
                "category": "malformed-currency-shape",
                "row_id": "row-3",
                "field": "unit_price",
                "expected": "21.00",
                "observed": "$21:00",
                "predicate": "raw token must match canonical money regex",
                "position_index": 0,
            }
        ],
        "row_reasons": {
            "row-3": {
                "categories": ["malformed-currency-shape"],
                "reason": "unit_price token '$21:00' fails canonical money regex",
            }
        },
        "supporting_evidence": {
            "body_confidence_mean": 0.970812,
            "body_confidence_min": 0.94,
            "body_line_count": 32,
            "body_token_count": 241,
            "header_band_excluded": True,
        },
    }
    assert _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (d) Report with status=='unevaluable', failed_checks=[], body_confidence_min=0.0,
#     cause set, cause_detail optional
# ---------------------------------------------------------------------------


def test_d_accepts_unevaluable_status_with_zero_confidence_min(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "unevaluable",
        "failed_checks": [],
        "supporting_evidence": {
            # F3: body_confidence_min is ALWAYS a JSON number, never null —
            # emit 0.0 when body_line_count == 0.
            "body_confidence_mean": 0.0,
            "body_confidence_min": 0.0,
            "body_line_count": 0,
            "body_token_count": 0,
            "header_band_excluded": False,
        },
        "cause": "preprocess_output_missing",
        "cause_detail": "No preprocess_output.json found",
    }
    assert _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (e) status='FAILED' (uppercase) is rejected — must be snake_case verbatim (Q26 / MI-11)
# ---------------------------------------------------------------------------


def test_e_rejects_status_with_wrong_case(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "FAILED",
        "failed_checks": [],
        "supporting_evidence": {
            "body_confidence_mean": 0.0,
            "body_confidence_min": 0.0,
            "body_line_count": 0,
            "body_token_count": 0,
            "header_band_excluded": False,
        },
    }
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (f) supporting_evidence with extra key rejected (additionalProperties: false)
# ---------------------------------------------------------------------------


def test_f_rejects_supporting_evidence_extra_key(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = True
    doc["semantic_table_quality"] = {
        "status": "passed",
        "failed_checks": [],
        "supporting_evidence": {
            "body_confidence_mean": 0.97,
            "body_confidence_min": 0.94,
            "body_line_count": 1,
            "body_token_count": 1,
            "header_band_excluded": True,
            "extra_key_not_allowed": "boom",
        },
    }
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (g) failed_checks[].category not in the four kebab-case values rejected
# ---------------------------------------------------------------------------


def test_g_rejects_unknown_failed_check_category(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "failed",
        "failed_checks": [
            {
                "category": "not-a-real-category",
                "row_id": "row-1",
                "field": "unit_price",
                "expected": "21.00",
                "observed": "$21:00",
                "predicate": "...",
                "position_index": 0,
            }
        ],
        "row_reasons": {
            "row-1": {
                "categories": ["not-a-real-category"],
                "reason": "boom",
            }
        },
        "supporting_evidence": {
            "body_confidence_mean": 0.97,
            "body_confidence_min": 0.94,
            "body_line_count": 1,
            "body_token_count": 1,
            "header_band_excluded": True,
        },
    }
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (h) row_reasons as a JSON ARRAY rejected — must be object keyed by row_id (F1)
# ---------------------------------------------------------------------------


def test_h_rejects_row_reasons_as_array(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "failed",
        "failed_checks": [
            {
                "category": "malformed-currency-shape",
                "row_id": "row-1",
                "field": "unit_price",
                "expected": "21.00",
                "observed": "$21:00",
                "predicate": "...",
                "position_index": 0,
            }
        ],
        # F1 violation: row_reasons MUST be an object keyed by row_id, NOT an array
        "row_reasons": [
            {
                "row_id": "row-1",
                "categories": ["malformed-currency-shape"],
                "reason": "boom",
            }
        ],
        "supporting_evidence": {
            "body_confidence_mean": 0.97,
            "body_confidence_min": 0.94,
            "body_line_count": 1,
            "body_token_count": 1,
            "header_band_excluded": True,
        },
    }
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# (i) row_reasons value missing `categories` or `reason` rejected (F2)
# ---------------------------------------------------------------------------


def test_i_rejects_row_reasons_value_missing_categories(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "failed",
        "failed_checks": [
            {
                "category": "malformed-currency-shape",
                "row_id": "row-1",
                "field": "unit_price",
                "expected": "21.00",
                "observed": "$21:00",
                "predicate": "...",
                "position_index": 0,
            }
        ],
        "row_reasons": {
            "row-1": {
                # F2 violation: missing `categories` field
                "reason": "boom",
            }
        },
        "supporting_evidence": {
            "body_confidence_mean": 0.97,
            "body_confidence_min": 0.94,
            "body_line_count": 1,
            "body_token_count": 1,
            "header_band_excluded": True,
        },
    }
    assert not _is_valid(validator, doc)


def test_i_rejects_row_reasons_value_missing_reason(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = False
    doc["semantic_table_quality"] = {
        "status": "failed",
        "failed_checks": [
            {
                "category": "malformed-currency-shape",
                "row_id": "row-1",
                "field": "unit_price",
                "expected": "21.00",
                "observed": "$21:00",
                "predicate": "...",
                "position_index": 0,
            }
        ],
        "row_reasons": {
            "row-1": {
                # F2 violation: missing `reason` field
                "categories": ["malformed-currency-shape"],
            }
        },
        "supporting_evidence": {
            "body_confidence_mean": 0.97,
            "body_confidence_min": 0.94,
            "body_line_count": 1,
            "body_token_count": 1,
            "header_band_excluded": True,
        },
    }
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# Plus: semantic_table_quality_passed value-domain (MI-17 / Q20).
# Each of the four values { true, false, null } must validate.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [True, False, None])
def test_semantic_table_quality_passed_accepts_boolean_or_null(
    validator: Draft202012Validator, value
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = value
    assert _is_valid(validator, doc)


def test_semantic_table_quality_passed_rejects_string(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = "true"
    assert not _is_valid(validator, doc)


def test_semantic_table_quality_passed_rejects_integer(
    validator: Draft202012Validator,
) -> None:
    doc = _base_doc()
    doc["document_pass_fail"]["semantic_table_quality_passed"] = 1
    assert not _is_valid(validator, doc)
