"""T027 / FR-009 / FR-011 / FR-012 / Q17 / Q18 — check predicate tests.

The four predicates are evaluated for every row in fixed Q17 order with
no short-circuit:
  1. malformed-currency-shape
  2. missing-required-content
  3. row-text-coverage-gap
  4. row-alignment-failure

Q18: predicate-based attribution — a row may record more than one
failed category when more than one predicate is true.
"""

from __future__ import annotations

from dartwing_ocr.evaluator.semantic_quality_anchor import RowAnchor, anchor_rows
from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    BodyOcrEvidence,
    BodyOcrLine,
)
from dartwing_ocr.evaluator.semantic_quality_checks import evaluate_all_rows
from dartwing_ocr.evaluator.semantic_quality_normalize import normalize


def _line(raw: str, page: int = 0, line: int = 0, conf: float = 0.97) -> BodyOcrLine:
    return BodyOcrLine(
        raw_text=raw,
        detector_confidence=conf,
        page_index=page,
        line_index=line,
        raw_tokens=raw.split(),
    )


def _evidence(lines: list[BodyOcrLine]) -> BodyOcrEvidence:
    joined = " ".join(line.raw_text for line in lines)
    return BodyOcrEvidence(
        included_lines=lines,
        excluded_line_count=0,
        normalized_search_string=normalize(joined),
        header_band_excluded=False,
    )


class _Row:
    """Lightweight row stand-in carrying sidecar fields."""

    def __init__(
        self,
        row_id: str,
        required_row_text_tokens: list[str],
        quantity: str | None = None,
        description: str | None = None,
        unit_price: str | None = None,
        amount: str | None = None,
    ) -> None:
        self.row_id = row_id
        self.required_row_text_tokens = required_row_text_tokens
        self.quantity = quantity
        self.description = description
        self.unit_price = unit_price
        self.amount = amount


class TestNoShortCircuit:
    def test_all_four_predicates_evaluated_per_row(self) -> None:
        """A row with multiple defects records ALL applicable failures (Q18 / MI-3)."""
        lines = [
            _line("Widget A description $21:00 missing-amount-line"),
        ]
        ev = _evidence(lines)
        # Row declares unit_price=21.00 (currency-shape will fail on $21:00),
        # quantity=4 (missing — not present in body),
        # required tokens include "Annual" (absent from body — coverage gap).
        rows = [
            _Row(
                row_id="row-1",
                required_row_text_tokens=["Widget", "Annual"],
                quantity="4",
                unit_price="21.00",
            )
        ]
        failed = evaluate_all_rows(rows, ev)
        cats = [fc.category for fc in failed]
        # At minimum these three categories should fire on row-1:
        assert "malformed-currency-shape" in cats
        assert "missing-required-content" in cats
        assert "row-text-coverage-gap" in cats


class TestFixedOrdering:
    def test_failed_checks_emitted_in_fixed_q17_order_per_row(self) -> None:
        lines = [_line("Widget $21:00 partial")]
        ev = _evidence(lines)
        rows = [
            _Row(
                row_id="row-1",
                required_row_text_tokens=["Widget", "MissingToken"],
                quantity="999",
                unit_price="21.00",
            )
        ]
        failed = evaluate_all_rows(rows, ev)
        # All failed_checks for row-1 must appear in this category order:
        # currency-shape → missing-content → coverage-gap → alignment
        order = [
            "malformed-currency-shape",
            "missing-required-content",
            "row-text-coverage-gap",
            "row-alignment-failure",
        ]
        row1_failures = [fc for fc in failed if fc.row_id == "row-1"]
        # The recorded categories should appear in the order specified,
        # filtered to only those present.
        emitted = [fc.category for fc in row1_failures]
        # Build the expected sub-sequence of `order` filtered to present
        # categories.
        expected_seq = [c for c in order if c in emitted]
        assert emitted == expected_seq

    def test_outer_iteration_is_sidecar_row_order(self) -> None:
        lines = [_line("X Y")]
        ev = _evidence(lines)
        rows = [
            _Row("row-A", required_row_text_tokens=["MissingA"], quantity="1"),
            _Row("row-B", required_row_text_tokens=["MissingB"], quantity="2"),
        ]
        failed = evaluate_all_rows(rows, ev)
        row_ids = [fc.row_id for fc in failed]
        # All row-A failures come before all row-B failures:
        if row_ids:
            first_b_idx = next((i for i, r in enumerate(row_ids) if r == "row-B"), len(row_ids))
            assert all(r == "row-A" for r in row_ids[:first_b_idx])


class TestPositionIndex:
    def test_position_index_zero_based_and_dense(self) -> None:
        lines = [_line("X")]
        ev = _evidence(lines)
        rows = [
            _Row("row-1", required_row_text_tokens=["Missing"], quantity="1"),
            _Row("row-2", required_row_text_tokens=["AlsoMissing"], quantity="2"),
        ]
        failed = evaluate_all_rows(rows, ev)
        for i, fc in enumerate(failed):
            assert fc.position_index == i


class TestBinaryRowTextCoverage:
    def test_single_missing_token_triggers_failure(self) -> None:
        """FR-011: binary — a single absent token triggers row-text-coverage-gap."""
        lines = [_line("Annual Maintenance Service")]
        ev = _evidence(lines)
        rows = [
            _Row(
                "row-1",
                required_row_text_tokens=["Annual", "Maintenance", "Contract"],
            )
        ]
        failed = evaluate_all_rows(rows, ev)
        coverage_failures = [fc for fc in failed if fc.category == "row-text-coverage-gap"]
        assert len(coverage_failures) >= 1

    def test_all_tokens_present_no_coverage_failure(self) -> None:
        lines = [_line("Annual Maintenance Contract Renewal")]
        ev = _evidence(lines)
        rows = [_Row("row-1", required_row_text_tokens=["Annual", "Maintenance", "Contract"])]
        failed = evaluate_all_rows(rows, ev)
        coverage_failures = [fc for fc in failed if fc.category == "row-text-coverage-gap"]
        assert coverage_failures == []


class TestNoMutualExclusion:
    def test_row_with_currency_and_content_failures_both_recorded(self) -> None:
        """Q18: predicate-based — both fire when both predicates true."""
        lines = [_line("Widget $21:00")]
        ev = _evidence(lines)
        rows = [
            _Row(
                "row-1",
                required_row_text_tokens=["Widget"],
                description="NonexistentDescription",
                unit_price="21.00",
            )
        ]
        failed = evaluate_all_rows(rows, ev)
        cats = {fc.category for fc in failed}
        assert "malformed-currency-shape" in cats
        assert "missing-required-content" in cats


class TestNoFailureClean:
    def test_clean_row_records_zero_failures(self) -> None:
        lines = [
            _line("Annual Maintenance Contract qty 4 $21.00 total $84.00"),
        ]
        ev = _evidence(lines)
        rows = [
            _Row(
                row_id="row-1",
                required_row_text_tokens=["Annual", "Maintenance", "Contract"],
                quantity="4",
                unit_price="21.00",
                amount="84.00",
            )
        ]
        failed = evaluate_all_rows(rows, ev)
        # No failure expected.
        assert failed == []
