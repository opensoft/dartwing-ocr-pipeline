"""US1 per-document evaluator tests — covers AC#1–#7 and FR-019 input immutability."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from ledgerlinc_ocr.evaluator import (
    ContractSetVersionMismatchError,
    DocumentIdMismatchError,
    ResultLabel,
    evaluate_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def test_all_match_writes_schema_valid_output(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "all_match", tmp_path)
    outcome = evaluate_document(folder)
    assert outcome.ok is True
    assert outcome.output_path == folder / "evaluation_document.json"
    assert outcome.output_path.exists()
    ev = outcome.evaluation
    assert ev is not None
    assert ev.document_id == "inv_001_easy"
    assert ev.difficulty == "easy"
    assert ev.document_pass_fail.vendor_identity_passed is True
    assert ev.document_pass_fail.review_routing_passed is True
    assert ev.document_pass_fail.overall_passed is True
    assert ev.comparison_summary.field_accuracy == 1.0


def test_challenge_tags_propagate_verbatim(tmp_path: Path) -> None:
    """FR-003: evaluation.challenge_tags is copied from expected.json unchanged."""
    import json

    folder = _copy_fixture(FIXTURES / "label_coverage", tmp_path)
    expected_tags = tuple(
        json.loads((folder / "expected.json").read_text(encoding="utf-8")).get(
            "challenge_tags", []
        )
    )
    outcome = evaluate_document(folder)
    assert outcome.evaluation is not None
    assert outcome.evaluation.challenge_tags == expected_tags


def test_field_results_ordered_by_scored_fields(tmp_path: Path) -> None:
    from ledgerlinc_ocr.evaluator.scoring import SCORED_FIELDS

    folder = _copy_fixture(FIXTURES / "all_match", tmp_path)
    outcome = evaluate_document(folder)
    assert outcome.evaluation is not None
    names = tuple(fr.field_name for fr in outcome.evaluation.field_results)
    assert names == SCORED_FIELDS


def test_label_coverage(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "label_coverage", tmp_path)
    outcome = evaluate_document(folder)
    assert outcome.ok is True
    ev = outcome.evaluation
    assert ev is not None
    by_name = {fr.field_name: fr for fr in ev.field_results}

    assert by_name["company_name.value"].result is ResultLabel.MATCH
    assert by_name["tax_ids.ein"].result is ResultLabel.MISSING_PREDICTION
    assert by_name["website"].result is ResultLabel.UNEXPECTED_PREDICTION
    assert by_name["tax_ids.state_tax_id"].result is ResultLabel.NOT_APPLICABLE
    assert by_name["tax_ids.vat_id"].result is ResultLabel.NOT_APPLICABLE
    assert by_name["tax_ids.other_tax_id"].result is ResultLabel.NOT_APPLICABLE


def test_comparison_summary_identity(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "label_coverage", tmp_path)
    outcome = evaluate_document(folder)
    ev = outcome.evaluation
    assert ev is not None
    cs = ev.comparison_summary
    tallied = (
        cs.matched_field_count
        + cs.mismatched_field_count
        + cs.missing_prediction_count
        + cs.unexpected_prediction_count
    )
    partial = cs.applicable_field_count - tallied
    assert partial >= 0
    assert tallied + partial == cs.applicable_field_count


def test_missing_final_payload_raises_and_writes_nothing(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "hard_errors/missing_final_payload", tmp_path)
    expected_hash = _sha(folder / "expected.json")
    with pytest.raises(FileNotFoundError):
        evaluate_document(folder)
    assert not (folder / "evaluation_document.json").exists()
    assert _sha(folder / "expected.json") == expected_hash


def test_contract_set_drift_raises_and_writes_nothing(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "hard_errors/contract_set_drift", tmp_path)
    expected_hash = _sha(folder / "expected.json")
    final_hash = _sha(folder / "final_structured_payload.json")
    with pytest.raises(ContractSetVersionMismatchError):
        evaluate_document(folder)
    assert not (folder / "evaluation_document.json").exists()
    assert _sha(folder / "expected.json") == expected_hash
    assert _sha(folder / "final_structured_payload.json") == final_hash


def test_older_minor_inputs_accepted_under_newer_pin(tmp_path: Path) -> None:
    """FR-013 MINOR-forward compatibility: artifacts stamped at an older minor
    (here `1.0.0`) MUST evaluate cleanly under a newer pinned contract set
    (here the default `1.1.0`), because MINOR bumps are additive and the
    older artifact is a valid subset of the newer schema."""
    folder = _copy_fixture(FIXTURES / "all_match", tmp_path)
    import json

    for name in ("expected.json", "final_structured_payload.json"):
        path = folder / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["contract_set_version"] == "1.0.0"
    outcome = evaluate_document(folder)
    assert outcome.ok is True
    assert outcome.evaluation is not None


def test_document_id_mismatch_raises_and_writes_nothing(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "hard_errors/document_id_mismatch", tmp_path)
    expected_hash = _sha(folder / "expected.json")
    final_hash = _sha(folder / "final_structured_payload.json")
    with pytest.raises(DocumentIdMismatchError):
        evaluate_document(folder)
    assert not (folder / "evaluation_document.json").exists()
    assert _sha(folder / "expected.json") == expected_hash
    assert _sha(folder / "final_structured_payload.json") == final_hash


def test_clean_completion_preserves_input_hashes(tmp_path: Path) -> None:
    folder = _copy_fixture(FIXTURES / "all_match", tmp_path)
    expected_hash = _sha(folder / "expected.json")
    final_hash = _sha(folder / "final_structured_payload.json")
    evaluate_document(folder)
    assert _sha(folder / "expected.json") == expected_hash
    assert _sha(folder / "final_structured_payload.json") == final_hash


def test_evaluate_document_writes_only_inside_folder(tmp_path: Path) -> None:
    """FR-025 writable-file scope: a successful `evaluate_document` call
    writes exactly one file (`evaluation_document.json`) inside the supplied
    folder, and nothing anywhere else under `tmp_path`."""
    folder = _copy_fixture(FIXTURES / "all_match", tmp_path)
    # Fixture ships with a pre-built evaluation_document.json for other tests;
    # remove it so we measure actual writes, not overwrites.
    (folder / "evaluation_document.json").unlink(missing_ok=True)
    before = {p for p in tmp_path.rglob("*") if p.is_file()}

    evaluate_document(folder)

    after = {p for p in tmp_path.rglob("*") if p.is_file()}
    new_files = after - before
    assert new_files == {folder / "evaluation_document.json"}, (
        f"evaluate_document wrote outside target folder: {new_files}"
    )
