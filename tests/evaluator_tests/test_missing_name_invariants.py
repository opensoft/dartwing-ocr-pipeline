"""US4 missing-name invariants — FR-012 / SC-004 coverage."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ledgerlinc_ocr.evaluator import evaluate_document

FIXTURES = Path(__file__).parent / "fixtures"


def _run(fixture_path: Path, tmp_path: Path):
    dst = tmp_path / fixture_path.name
    shutil.copytree(fixture_path, dst)
    outcome = evaluate_document(dst)
    return outcome.evaluation


def test_missing_name_valid_passes(tmp_path: Path) -> None:
    """US4 AC#1: all four invariants satisfied → review_routing_passed=True, overall=True."""
    ev = _run(FIXTURES / "missing_name_valid", tmp_path)
    assert ev.document_pass_fail.review_routing_passed is True
    assert ev.document_pass_fail.vendor_identity_passed is True
    assert ev.document_pass_fail.overall_passed is True


@pytest.mark.parametrize(
    "violation",
    ["present_true", "inferred_false", "manual_review_false", "review_reason_wrong"],
)
def test_missing_name_violation_fails(violation: str, tmp_path: Path) -> None:
    """US4 AC#2/AC#3 + SC-004: any single invariant violation fails the gate."""
    ev = _run(FIXTURES / "missing_name_violations" / violation, tmp_path)
    assert ev.document_pass_fail.review_routing_passed is False
    assert ev.document_pass_fail.overall_passed is False


def test_present_true_also_fails_vendor_identity(tmp_path: Path) -> None:
    """US4 AC#2 specifically: `present == True` (expected False) is a mismatch on
    `company_name.present`, which alone kills vendor_identity_passed."""
    ev = _run(FIXTURES / "missing_name_violations" / "present_true", tmp_path)
    assert ev.document_pass_fail.vendor_identity_passed is False
