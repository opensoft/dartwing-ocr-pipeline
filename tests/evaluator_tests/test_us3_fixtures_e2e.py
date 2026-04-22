"""End-to-end coverage for US3 fixtures (T051/T052/T053).

Runs `evaluate_document` against each fixture folder and checks the expected
field-level ResultLabel and gate outcome. Each fixture is a minimal
expected.json + final_structured_payload.json pair.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ledgerlinc_ocr.evaluator import evaluate_document
from ledgerlinc_ocr.evaluator.scoring import ResultLabel

FIXTURES = Path(__file__).parent / "fixtures"


def _run(fixture_path: Path, tmp_path: Path):
    dst = tmp_path / fixture_path.name
    shutil.copytree(fixture_path, dst)
    outcome = evaluate_document(dst)
    return outcome.evaluation


def _result_map(evaluation) -> dict[str, ResultLabel]:
    return {fr.field_name: fr.result for fr in evaluation.field_results}


# --- T051 Normalization cases ------------------------------------------------


@pytest.mark.parametrize(
    "folder,field,expected_label",
    [
        ("state_full_vs_abbrev", "address.state", ResultLabel.MATCH),
        ("website_scheme_www", "website", ResultLabel.MATCH),
        ("email_case", "email", ResultLabel.MATCH),
        ("phone_digits_only", "phone", ResultLabel.MATCH),
        ("tax_id_hyphens", "tax_ids.ein", ResultLabel.MATCH),
        ("street_suffix", "address.street_1", ResultLabel.MATCH),
        ("company_suffix", "company_name.value", ResultLabel.MATCH),
        ("postal_exact", "address.postal_code", ResultLabel.MATCH),
    ],
)
def test_normalization_case(folder: str, field: str, expected_label: ResultLabel, tmp_path: Path) -> None:
    ev = _run(FIXTURES / "normalization_cases" / folder, tmp_path)
    assert _result_map(ev)[field] is expected_label


# --- T052 Partial-match cases ------------------------------------------------


@pytest.mark.parametrize(
    "folder,field,expected_label",
    [
        ("postal_zip4_vs_zip", "address.postal_code", ResultLabel.PARTIAL_MATCH),
        ("phone_with_extension", "phone", ResultLabel.PARTIAL_MATCH),
        ("street_imperfect", "address.street_1", ResultLabel.PARTIAL_MATCH),
        ("company_partial", "company_name.value", ResultLabel.PARTIAL_MATCH),
    ],
)
def test_partial_match_case(folder: str, field: str, expected_label: ResultLabel, tmp_path: Path) -> None:
    ev = _run(FIXTURES / "partial_match_cases" / folder, tmp_path)
    assert _result_map(ev)[field] is expected_label


# --- T053 Gate fixtures ------------------------------------------------------


def test_gate_score_high_but_vendor_identity_fails(tmp_path: Path) -> None:
    ev = _run(FIXTURES / "secondary_identifier_gates" / "score_ok_vendor_identity_fails", tmp_path)
    # company_name.value matches, present mismatches → vendor identity fails.
    assert _result_map(ev)["company_name.value"] is ResultLabel.MATCH
    assert _result_map(ev)["company_name.present"] is ResultLabel.MISMATCH
    assert ev.document_pass_fail.vendor_identity_passed is False
    assert ev.document_pass_fail.overall_passed is False
    # Score remains above 0.85 (weight 8 out of 100 lost).
    assert ev.document_score >= 0.85


def test_gate_only_one_slot_matches(tmp_path: Path) -> None:
    ev = _run(FIXTURES / "secondary_identifier_gates" / "only_one_slot_matches", tmp_path)
    assert ev.document_pass_fail.vendor_identity_passed is False


def test_gate_manual_review_flipped(tmp_path: Path) -> None:
    ev = _run(FIXTURES / "secondary_identifier_gates" / "manual_review_flipped", tmp_path)
    assert _result_map(ev)["manual_review_required"] is ResultLabel.MISMATCH
    assert ev.document_pass_fail.review_routing_passed is False
    assert ev.document_pass_fail.overall_passed is False
