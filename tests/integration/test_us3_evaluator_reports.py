"""T047 — US3 acceptance scenarios AS1-AS4.

US3: Surface semantic table quality in evaluator reports.

AS1: sidecar document → `evaluation_document.json` includes
     `semantic_table_quality` object with `status`, `failed_checks` (always
     present), `row_reasons` (object keyed by `row_id` when status==failed),
     `supporting_evidence`.
AS2: mixed corpus → `evaluation_run_summary.json` includes both top-level
     sibling keys `semantic_table_quality_metrics` AND
     `semantic_document_statuses` (per F6 — array, parallel to metrics),
     AND vendor-identity pass rates comparable to prior runs.
AS3: pre-feature report still loads (FR-019 / SC-008).
AS4: existing vendor-identity metric values unchanged (FR-020).

These tests build minimal in-memory inputs and exercise the writer
integration directly — they do NOT depend on the full corpus harness.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from dartwing_ocr.evaluator import evaluate_corpus, evaluate_document
from dartwing_ocr.evaluator.schema import (
    load_evaluation_document_schema,
    load_evaluation_run_summary_schema,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_EVALUATOR_FIXTURES = REPO_ROOT / "tests" / "evaluator_tests" / "fixtures"
_SEMANTIC_FIXTURE = REPO_ROOT / "tests" / "stage1_semantic_quality" / "inv_001_hard"


# ---------------------------------------------------------------------------
# AS1: sidecar document → evaluation_document.json includes semantic_table_quality
# ---------------------------------------------------------------------------


def test_as1_sidecar_document_eval_doc_includes_semantic_table_quality(
    tmp_path: Path,
) -> None:
    """AS1: A per-document folder that has a semantic_table_truth.json sidecar
    AND a preprocess_output.json produces an evaluation_document.json whose
    `semantic_table_quality` object is present with the closed shape."""
    # Build a per-document folder by copying an existing fixture and dropping
    # the semantic fixture's sidecar + preprocess_output.json into it.
    src = _EVALUATOR_FIXTURES / "all_match"
    folder = tmp_path / "inv_001_hard"
    shutil.copytree(src, folder)

    # Rewrite the fixture's document_id to match the folder basename so the
    # semantic gate's folder_basename matches the sidecar's document_id.
    for filename in ("expected.json", "final_structured_payload.json"):
        path = folder / filename
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["document_id"] = "inv_001_hard"
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    # Stage the semantic fixture inputs into the per-doc folder.
    shutil.copy(_SEMANTIC_FIXTURE / "preprocess_output.json", folder)
    shutil.copy(_SEMANTIC_FIXTURE / "semantic_table_truth.json", folder)

    # Run the per-document evaluator.
    evaluate_document(folder)

    eval_path = folder / "evaluation_document.json"
    instance = json.loads(eval_path.read_text(encoding="utf-8"))

    # Schema-valid under v1.3.0
    Draft202012Validator(load_evaluation_document_schema()).validate(instance)

    # semantic_table_quality object present with closed shape
    assert "semantic_table_quality" in instance
    stq = instance["semantic_table_quality"]
    assert stq["status"] in {"passed", "failed", "unevaluable"}
    # failed_checks is ALWAYS present (F5 resolution)
    assert "failed_checks" in stq
    assert isinstance(stq["failed_checks"], list)
    # supporting_evidence is always present when status is in the evaluable set
    assert "supporting_evidence" in stq
    se = stq["supporting_evidence"]
    # body_confidence_min is ALWAYS a float (F3 resolution)
    assert isinstance(se["body_confidence_min"], (int, float))
    assert isinstance(se["body_confidence_mean"], (int, float))

    # When failed, row_reasons is an OBJECT keyed by row_id with {categories, reason}
    if stq["status"] == "failed":
        assert "row_reasons" in stq
        assert isinstance(stq["row_reasons"], dict)
        for row_id, entry in stq["row_reasons"].items():
            assert isinstance(row_id, str)
            assert "categories" in entry
            assert "reason" in entry

    # document_pass_fail.semantic_table_quality_passed is always present
    # and follows the MI-17 value-domain mapping.
    pf = instance["document_pass_fail"]
    assert "semantic_table_quality_passed" in pf
    status = stq["status"]
    if status == "passed":
        assert pf["semantic_table_quality_passed"] is True
    elif status in {"failed", "unevaluable"}:
        assert pf["semantic_table_quality_passed"] is False


# ---------------------------------------------------------------------------
# AS2: mixed corpus → run_summary has both metrics + statuses keys
# ---------------------------------------------------------------------------


def test_as2_mixed_corpus_run_summary_has_both_top_level_semantic_keys(
    tmp_path: Path,
) -> None:
    """AS2: After running over a mixed corpus (at least one sidecar
    document + at least one without), `evaluation_run_summary.json` MUST
    include BOTH top-level sibling keys: `semantic_table_quality_metrics`
    AND `semantic_document_statuses` (per F6 resolution)."""
    root = tmp_path / "corpus"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root)

    # Drop the sidecar + preprocess into ONE of the folders so we get a
    # mixed corpus (some with semantic data, some without).
    folders = sorted(p for p in root.iterdir() if p.is_dir())
    assert len(folders) >= 2
    target = folders[0]
    # Rewrite document_id to align with the folder basename — required so
    # the sidecar's document_id matches the folder.
    sidecar = json.loads(
        (_SEMANTIC_FIXTURE / "semantic_table_truth.json").read_text(encoding="utf-8")
    )
    sidecar["document_id"] = target.name
    (target / "semantic_table_truth.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy(_SEMANTIC_FIXTURE / "preprocess_output.json", target)

    evaluate_corpus(root)

    summary_path = root / "evaluation_run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    Draft202012Validator(load_evaluation_run_summary_schema()).validate(summary)

    # Both keys at TOP LEVEL (NOT nested) per F6 resolution
    assert "semantic_table_quality_metrics" in summary
    assert "semantic_document_statuses" in summary
    # F6: NOT nested
    assert "semantic_document_statuses" not in summary["semantic_table_quality_metrics"]

    # Metrics namespace has all 8 fields
    metrics = summary["semantic_table_quality_metrics"]
    expected = {
        "semantic_applicable_document_count",
        "semantic_not_applicable_document_count",
        "semantic_evaluable_document_count",
        "semantic_passed_document_count",
        "semantic_failed_document_count",
        "semantic_unevaluable_document_count",
        "semantic_table_quality_pass_rate",
        "semantic_failed_check_counts",
    }
    assert set(metrics.keys()) == expected

    # semantic_document_statuses is a list of per-document entries; the
    # target folder is in it with a non-null status; the others are
    # not_applicable with null passed.
    statuses = summary["semantic_document_statuses"]
    assert isinstance(statuses, list)
    by_id = {s["document_id"]: s for s in statuses}
    # The target document — sidecar was present
    assert by_id[target.name]["semantic_table_quality_status"] in {
        "passed",
        "failed",
        "unevaluable",
    }
    # An untouched neighbor folder should be not_applicable
    untouched = folders[1]
    assert by_id[untouched.name]["semantic_table_quality_status"] == "not_applicable"
    assert by_id[untouched.name]["semantic_table_quality_passed"] is None


# ---------------------------------------------------------------------------
# AS3: pre-feature report still loads (FR-019 / SC-008)
# ---------------------------------------------------------------------------


def test_as3_pre_feature_eval_doc_still_loads(tmp_path: Path) -> None:
    """FR-019 / SC-008: A pre-feature evaluation_document.json (no semantic
    fields) can still be read by the backward-compat reader without error."""
    from dartwing_ocr.validator.artifact import read_semantic_table_quality_passed

    # Hand-author a pre-feature evaluation_document.json (no semantic_*).
    pre_feature = {
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
    path = tmp_path / "evaluation_document.json"
    path.write_text(json.dumps(pre_feature, indent=2) + "\n", encoding="utf-8")

    # Validates under v1.3.0 schema (additive keys are optional)
    instance = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(load_evaluation_document_schema()).validate(instance)

    # The backward-compat reader returns None for the absent field
    assert read_semantic_table_quality_passed(instance) is None


def test_as3_pre_feature_run_summary_still_loads() -> None:
    """The v1.3.0 schema accepts an evaluation_run_summary.json with no
    semantic_table_quality_metrics and no semantic_document_statuses."""
    pre_feature = {
        "contract_set_version": "1.2.0",
        "run_id": "run_legacy",
        "document_count": 0,
        "overall_metrics": {
            "field_accuracy": 1.0,
            "vendor_identity_pass_rate": 1.0,
            "review_routing_pass_rate": 1.0,
            "overall_document_pass_rate": 1.0,
        },
        "consensus_metrics": {
            "single_voter_baseline_runs": 0,
            "majority_vote_documents": 0,
            "split_decision_documents": 0,
        },
        "by_difficulty": {
            "easy": {
                "document_count": 0,
                "field_accuracy": 0.0,
                "overall_document_pass_rate": 0.0,
            },
            "medium": {
                "document_count": 0,
                "field_accuracy": 0.0,
                "overall_document_pass_rate": 0.0,
            },
            "hard": {
                "document_count": 0,
                "field_accuracy": 0.0,
                "overall_document_pass_rate": 0.0,
            },
            "missing_name": {
                "document_count": 0,
                "field_accuracy": 0.0,
                "overall_document_pass_rate": 0.0,
            },
        },
        "by_field": {},
        "documents": [],
    }
    Draft202012Validator(load_evaluation_run_summary_schema()).validate(pre_feature)


# ---------------------------------------------------------------------------
# AS4: existing vendor-identity metric values unchanged (FR-020)
# ---------------------------------------------------------------------------


def test_as4_vendor_identity_metrics_unchanged_after_feature(tmp_path: Path) -> None:
    """FR-020 / MI-22: The presence of the new semantic_table_quality_metrics
    namespace MUST NOT change any vendor-identity metric value on the run
    summary. Compare the vendor-identity portion of two runs: one with a
    sidecar present, one without — vendor-identity portions MUST match."""
    root_no_sidecar = tmp_path / "no_sidecar"
    root_with_sidecar = tmp_path / "with_sidecar"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root_no_sidecar)
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root_with_sidecar)

    # Add a sidecar (+ preprocess) to one folder in the "with_sidecar" corpus
    folders = sorted(p for p in root_with_sidecar.iterdir() if p.is_dir())
    target = folders[0]
    sidecar = json.loads(
        (_SEMANTIC_FIXTURE / "semantic_table_truth.json").read_text(encoding="utf-8")
    )
    sidecar["document_id"] = target.name
    (target / "semantic_table_truth.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copy(_SEMANTIC_FIXTURE / "preprocess_output.json", target)

    evaluate_corpus(root_no_sidecar)
    evaluate_corpus(root_with_sidecar)

    no_sidecar_summary = json.loads(
        (root_no_sidecar / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )
    with_sidecar_summary = json.loads(
        (root_with_sidecar / "evaluation_run_summary.json").read_text(encoding="utf-8")
    )

    # Vendor-identity portion must be identical — same overall_metrics,
    # by_difficulty, by_field, documents, consensus_metrics, document_count.
    vendor_keys = (
        "overall_metrics",
        "consensus_metrics",
        "by_difficulty",
        "by_field",
        "documents",
        "document_count",
    )
    for key in vendor_keys:
        assert no_sidecar_summary[key] == with_sidecar_summary[key], (
            f"vendor-identity key '{key}' changed after sidecar added — "
            f"FR-020 / MI-22 violation"
        )


def test_as4_existing_vendor_identity_eval_doc_unchanged_with_no_sidecar(
    tmp_path: Path,
) -> None:
    """A folder with NO sidecar produces an evaluation_document.json whose
    vendor-identity portion is byte-identical to the pre-feature shape (only
    `document_pass_fail.semantic_table_quality_passed: null` is added)."""
    src = _EVALUATOR_FIXTURES / "all_match"
    folder = tmp_path / "inv_no_sidecar"
    shutil.copytree(src, folder)

    evaluate_document(folder)
    instance = json.loads(
        (folder / "evaluation_document.json").read_text(encoding="utf-8")
    )

    # Schema valid
    Draft202012Validator(load_evaluation_document_schema()).validate(instance)

    # semantic_table_quality KEY absent (status would be not_applicable)
    assert "semantic_table_quality" not in instance

    # semantic_table_quality_passed: null on document_pass_fail
    assert instance["document_pass_fail"]["semantic_table_quality_passed"] is None

    # Existing vendor-identity fields untouched
    assert instance["document_pass_fail"]["vendor_identity_passed"] in {True, False}
    assert "overall_passed" in instance["document_pass_fail"]
    assert "review_routing_passed" in instance["document_pass_fail"]
