"""T044 (US3): contract-level tests for the v1.3.0 ``evaluation_run_summary.schema.json``.

Validates that the additive top-level keys land correctly:

- ``semantic_table_quality_metrics`` (Q36): closed shape with all 8 fields
- ``semantic_document_statuses`` (F6): TOP-LEVEL sibling array — NOT nested
  inside ``semantic_table_quality_metrics``
- ``semantic_table_quality_pass_rate: null`` when evaluable=0 is accepted
- Closed-shape additionalProperties rules on both keys
- Closed enum on ``semantic_table_quality_status`` per Q26 / MI-11
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
    / "evaluation_run_summary.schema.json"
)


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _is_valid(validator: Draft202012Validator, doc: dict) -> bool:
    return not list(validator.iter_errors(doc))


def _base_summary(**overrides) -> dict:
    """Build a minimal-valid v1.3.0 evaluation_run_summary.json shell.

    Thin wrapper around the shared helper (deduped per Sonar duplication
    finding on PR #47 2026-05-23).
    """
    from helpers.evaluation_artifacts import build_minimal_evaluation_run_summary
    return build_minimal_evaluation_run_summary(**overrides)


def _full_metrics(**overrides) -> dict:
    metrics = {
        "semantic_applicable_document_count": 1,
        "semantic_not_applicable_document_count": 19,
        "semantic_evaluable_document_count": 1,
        "semantic_passed_document_count": 0,
        "semantic_failed_document_count": 1,
        "semantic_unevaluable_document_count": 0,
        "semantic_table_quality_pass_rate": 0.0,
        "semantic_failed_check_counts": {
            "malformed-currency-shape": 1,
            "missing-required-content": 1,
            "row-text-coverage-gap": 1,
            "row-alignment-failure": 0,
        },
    }
    metrics.update(overrides)
    return metrics


# ---------------------------------------------------------------------------
# semantic_table_quality_metrics — 8-field closed shape
# ---------------------------------------------------------------------------


def test_accepts_full_metrics_namespace(validator: Draft202012Validator) -> None:
    doc = _base_summary(semantic_table_quality_metrics=_full_metrics())
    assert _is_valid(validator, doc)


def test_accepts_null_pass_rate_when_evaluable_zero(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_table_quality_metrics=_full_metrics(
            semantic_applicable_document_count=0,
            semantic_evaluable_document_count=0,
            semantic_passed_document_count=0,
            semantic_failed_document_count=0,
            semantic_table_quality_pass_rate=None,
        )
    )
    assert _is_valid(validator, doc)


def test_rejects_metrics_with_extra_unknown_key(
    validator: Draft202012Validator,
) -> None:
    bad = _full_metrics()
    bad["bogus_extra_key"] = 42
    doc = _base_summary(semantic_table_quality_metrics=bad)
    assert not _is_valid(validator, doc)


def test_rejects_failed_check_counts_with_unknown_category(
    validator: Draft202012Validator,
) -> None:
    bad = _full_metrics()
    bad["semantic_failed_check_counts"]["not-a-real-category"] = 1
    doc = _base_summary(semantic_table_quality_metrics=bad)
    assert not _is_valid(validator, doc)


def test_rejects_failed_check_counts_missing_required_category(
    validator: Draft202012Validator,
) -> None:
    bad = _full_metrics()
    del bad["semantic_failed_check_counts"]["row-alignment-failure"]
    doc = _base_summary(semantic_table_quality_metrics=bad)
    assert not _is_valid(validator, doc)


def test_rejects_metrics_missing_required_field(
    validator: Draft202012Validator,
) -> None:
    bad = _full_metrics()
    del bad["semantic_passed_document_count"]
    doc = _base_summary(semantic_table_quality_metrics=bad)
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# semantic_document_statuses — TOP-LEVEL sibling array (F6 pin)
# ---------------------------------------------------------------------------


def test_accepts_semantic_document_statuses_as_top_level_sibling(
    validator: Draft202012Validator,
) -> None:
    """F6 pin: semantic_document_statuses is a TOP-LEVEL sibling array, NOT
    nested inside semantic_table_quality_metrics."""
    doc = _base_summary(
        semantic_table_quality_metrics=_full_metrics(),
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_status": "failed",
                "semantic_table_quality_passed": False,
            },
            {
                "document_id": "inv_002_easy",
                "semantic_table_quality_status": "not_applicable",
                "semantic_table_quality_passed": None,
            },
        ],
    )
    assert _is_valid(validator, doc)


@pytest.mark.parametrize(
    "status,passed",
    [
        ("passed", True),
        ("failed", False),
        ("unevaluable", False),
        ("not_applicable", None),
    ],
)
def test_accepts_each_status_with_correct_passed(
    validator: Draft202012Validator, status: str, passed
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_status": status,
                "semantic_table_quality_passed": passed,
            }
        ],
    )
    assert _is_valid(validator, doc)


def test_rejects_unknown_semantic_status_string(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_status": "PASSED",
                "semantic_table_quality_passed": True,
            }
        ],
    )
    assert not _is_valid(validator, doc)


def test_rejects_status_entry_missing_document_id(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "semantic_table_quality_status": "passed",
                "semantic_table_quality_passed": True,
            }
        ],
    )
    assert not _is_valid(validator, doc)


def test_rejects_status_entry_missing_status_field(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_passed": True,
            }
        ],
    )
    assert not _is_valid(validator, doc)


def test_rejects_status_entry_missing_passed_field(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_status": "passed",
            }
        ],
    )
    assert not _is_valid(validator, doc)


def test_rejects_status_entry_with_extra_property(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_status": "passed",
                "semantic_table_quality_passed": True,
                "extra_key": "boom",
            }
        ],
    )
    assert not _is_valid(validator, doc)


# ---------------------------------------------------------------------------
# Sanity: both new keys are independently OPTIONAL for FR-019 backward-compat
# ---------------------------------------------------------------------------


def test_accepts_summary_without_any_semantic_keys(
    validator: Draft202012Validator,
) -> None:
    """Pre-feature run summaries (no semantic keys) MUST still validate."""
    doc = _base_summary()
    assert _is_valid(validator, doc)


def test_accepts_summary_with_only_metrics_no_statuses(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(semantic_table_quality_metrics=_full_metrics())
    assert _is_valid(validator, doc)


def test_accepts_summary_with_only_statuses_no_metrics(
    validator: Draft202012Validator,
) -> None:
    doc = _base_summary(
        semantic_document_statuses=[
            {
                "document_id": "inv_001_hard",
                "semantic_table_quality_status": "passed",
                "semantic_table_quality_passed": True,
            }
        ],
    )
    assert _is_valid(validator, doc)
