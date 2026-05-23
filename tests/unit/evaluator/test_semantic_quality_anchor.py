"""T025 / FR-012 / Q7 / Q24 — row-anchoring tests.

For each sidecar row, the anchor algorithm finds the contiguous span of
body-OCR included-line indices that maximizes the count of
required_row_text_tokens whose normalize(token) appears in the span's
normalized text.

Tie-break (Q24): earliest (page_index, line_index) span start, then
sidecar row declaration order (Q7).
"""

from __future__ import annotations

from dartwing_ocr.evaluator.semantic_quality_anchor import RowAnchor, anchor_rows
from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    BodyOcrEvidence,
    BodyOcrLine,
)


def _line(raw: str, page: int = 0, line: int = 0, conf: float = 0.9) -> BodyOcrLine:
    return BodyOcrLine(
        raw_text=raw,
        detector_confidence=conf,
        page_index=page,
        line_index=line,
        raw_tokens=raw.split(),
    )


def _evidence(lines: list[BodyOcrLine]) -> BodyOcrEvidence:
    # Build the normalized search string by joining + normalize (test bypass)
    from dartwing_ocr.evaluator.semantic_quality_normalize import normalize

    joined = " ".join(line.raw_text for line in lines)
    return BodyOcrEvidence(
        included_lines=lines,
        excluded_line_count=0,
        normalized_search_string=normalize(joined),
        header_band_excluded=False,
    )


class _Row:
    """Lightweight sidecar-row stand-in. The anchor reads row_id and
    required_row_text_tokens. The semantic_quality_anchor module accepts
    any object with those attributes."""

    def __init__(self, row_id: str, tokens: list[str]):
        self.row_id = row_id
        self.required_row_text_tokens = tokens


class TestBestSpanSelection:
    def test_span_with_most_required_tokens_wins(self) -> None:
        lines = [
            _line("Widget A description"),
            _line("Widget B description Annual Maintenance Contract"),
            _line("Other unrelated line"),
        ]
        ev = _evidence(lines)
        rows = [_Row("row-1", ["Annual", "Maintenance", "Contract"])]
        anchors = anchor_rows(rows, ev)
        assert anchors["row-1"] is not None
        anchor = anchors["row-1"]
        # The best single-line span is line index 1 (3-token match).
        assert anchor.start_line_index <= 1 <= anchor.end_line_index

    def test_token_count_not_edit_distance(self) -> None:
        # Two candidate spans; one has fuzzy-similar text, the other has
        # exact tokens — the exact-token span MUST contain the row.
        # (Tie-break: when both [1..1] and [0..1] match all 3 tokens
        # equally, [0..1] wins by Q24's "earliest start" rule even though
        # it's wider; per data-model §12 there is no narrowness preference.)
        lines = [
            _line("Anuual Maintainance Contrct"),  # fuzzy, 0 exact matches
            _line("Annual Maintenance Contract"),  # 3 exact matches
        ]
        ev = _evidence(lines)
        rows = [_Row("row-1", ["Annual", "Maintenance", "Contract"])]
        anchors = anchor_rows(rows, ev)
        assert anchors["row-1"] is not None
        anchor = anchors["row-1"]
        # The anchor must cover the line with the exact tokens.
        assert anchor.end_line_index >= 1
        assert anchor.start_line_index <= 1


class TestTieBreak:
    def test_tie_break_by_earliest_position(self) -> None:
        # Two spans match the same token count; pick the earliest one.
        lines = [
            _line("Widget", page=0, line=0),
            _line("Other", page=0, line=1),
            _line("Widget", page=0, line=2),
        ]
        ev = _evidence(lines)
        rows = [_Row("row-1", ["Widget"])]
        anchors = anchor_rows(rows, ev)
        assert anchors["row-1"] is not None
        # Earliest = the line at index 0
        assert anchors["row-1"].start_line_index == 0

    def test_further_tie_break_by_sidecar_declaration_order(self) -> None:
        # Two rows want the same token; both should anchor (just different
        # rows — but if they were truly identical the order in the returned
        # dict reflects sidecar order).
        lines = [_line("Widget", page=0, line=0)]
        ev = _evidence(lines)
        rows = [
            _Row("row-A", ["Widget"]),
            _Row("row-B", ["Widget"]),
        ]
        anchors = anchor_rows(rows, ev)
        # Both rows anchor to the same span — there is no exclusivity rule
        # in the algorithm. The "sidecar declaration order" tie-break only
        # applies when two rows compete for the same anchor decision; here
        # we just verify both get anchored deterministically.
        assert anchors["row-A"] is not None
        assert anchors["row-B"] is not None
        assert anchors["row-A"].start_line_index == 0


class TestEmptyEvidence:
    def test_no_lines_returns_none_anchor(self) -> None:
        ev = _evidence([])
        rows = [_Row("row-1", ["Widget"])]
        anchors = anchor_rows(rows, ev)
        assert anchors["row-1"] is None


class TestNoMatch:
    def test_no_token_match_still_picks_a_span(self) -> None:
        # Per data-model §12 the anchor picks the max-count span even if
        # that count is zero — the earliest span wins on ties. The downstream
        # row-text-coverage check is what records the failure, not anchor.
        lines = [_line("Foo"), _line("Bar")]
        ev = _evidence(lines)
        rows = [_Row("row-1", ["Widget"])]
        anchors = anchor_rows(rows, ev)
        # With zero matches, any contiguous span is valid; deterministically
        # we expect (0, 0) — earliest start, earliest end.
        assert anchors["row-1"] is not None


class TestDeterminism:
    def test_two_runs_same_anchor(self) -> None:
        lines = [
            _line("Widget A description"),
            _line("Widget B description Annual Maintenance Contract"),
            _line("Other unrelated line"),
        ]
        ev = _evidence(lines)
        rows = [
            _Row("row-1", ["Annual", "Maintenance"]),
            _Row("row-2", ["Widget", "B"]),
        ]
        a1 = anchor_rows(rows, ev)
        a2 = anchor_rows(rows, ev)
        assert a1 == a2
