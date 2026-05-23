"""T024 / Q22 / R-022.4 — body-OCR evidence build tests.

Body OCR comes from every page's raw_ocr_lines in preprocess_output.json
serialization order EXCEPT the page-1 header band (lines with bbox top-y
fraction < Y_THRESHOLD_FRACTION = 0.25 of page height).

Per MI-7: the constant is imported from
preprocessing.evidence_gate as EVIDENCE_GATE_Y_THRESHOLD_FRACTION.

bbox shape is [x1, y1, x2, y2] per preprocess_output.schema.json (and per
preprocessing.evidence_gate._bbox_top_y). Lane-robust: same answer for
OCR-only and PPStructureV3 outputs.
"""

from __future__ import annotations

import pytest

from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    EVIDENCE_GATE_Y_THRESHOLD_FRACTION,
    BodyOcrEvidence,
    BodyOcrLine,
    build_body_ocr_evidence,
)
from dartwing_ocr.preprocessing import evidence_gate as _eg


def _line(line_id: str, x1: int, y1: int, x2: int, y2: int, text: str, conf: float) -> dict:
    return {
        "line_id": line_id,
        "bbox": [x1, y1, x2, y2],
        "text": text,
        "confidence": conf,
    }


def _page(page_number: int, height: int, lines: list[dict]) -> dict:
    return {
        "page_number": page_number,
        "width": 2550,
        "height": height,
        "rotation_detected": 0,
        "blocks": [],
        "raw_ocr_lines": lines,
    }


def _preprocess(pages: list[dict]) -> dict:
    return {
        "contract_set_version": "1.3.0",
        "pipeline_version": "test",
        "document_id": "test_doc",
        "source_type": "pdf",
        "source_file": "x.pdf",
        "page_count": len(pages),
        "pages": pages,
        "document_text": "",
        "tables": [],
        "quality": {"scan_quality": "good", "skew_detected": False, "noise_level": "low"},
        "ingestion_sources": {
            "paddleocr_vl": {"enabled": True, "status": "success"},
            "falcon_ocr": {"enabled": False, "status": "not_implemented"},
            "falcon_perception": {"enabled": False, "status": "not_implemented"},
        },
        "warnings": [],
    }


class TestMiSevenImportedConstant:
    def test_y_threshold_re_exported_from_evidence_gate(self) -> None:
        """MI-7: constant comes from preprocessing.evidence_gate, not local."""
        # `is` would also work since both names bind to the same Python
        # float literal, but `==` keeps the test readable. The second
        # check uses pytest.approx to satisfy Sonar python:S1244 (no
        # float equality) without changing the test semantics.
        assert EVIDENCE_GATE_Y_THRESHOLD_FRACTION == _eg.Y_THRESHOLD_FRACTION
        assert EVIDENCE_GATE_Y_THRESHOLD_FRACTION == pytest.approx(0.25)


class TestHeaderBandExclusion:
    def test_page1_line_below_threshold_excluded(self) -> None:
        # height=1000, threshold y = 250. Top-y = 100 < 250 → excluded.
        page = _page(1, 1000, [_line("p1_l1", 0, 100, 100, 150, "HEADER", 0.99)])
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert ev.excluded_line_count == 1
        assert list(ev.included_lines) == []
        assert ev.header_band_excluded is True

    def test_page1_line_at_threshold_included(self) -> None:
        # Top-y = 250 → threshold_y = 250 → "strictly less than" excludes, so
        # y == threshold means INCLUDED (per evidence_gate._band_blocks).
        page = _page(1, 1000, [_line("p1_l1", 0, 250, 100, 300, "BODY", 0.99)])
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert ev.excluded_line_count == 0
        assert len(ev.included_lines) == 1
        assert ev.header_band_excluded is False

    def test_page1_line_above_threshold_included(self) -> None:
        page = _page(1, 1000, [_line("p1_l1", 0, 500, 100, 600, "BODY", 0.99)])
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert ev.excluded_line_count == 0
        assert len(ev.included_lines) == 1

    def test_page2_line_always_included_regardless_of_y(self) -> None:
        """Per R-022.4: lines on pages 2..N are fully included regardless of y."""
        page1 = _page(1, 1000, [_line("p1_l1", 0, 500, 100, 600, "P1-BODY", 0.99)])
        # Page 2 has a low-y line that WOULD be excluded if the rule applied
        page2 = _page(2, 1000, [_line("p2_l1", 0, 50, 100, 100, "P2-TOP", 0.99)])
        ev = build_body_ocr_evidence(_preprocess([page1, page2]))
        assert len(ev.included_lines) == 2
        assert ev.included_lines[1].raw_text == "P2-TOP"
        assert ev.included_lines[1].page_index == 1

    def test_header_band_excluded_true_when_any_excluded(self) -> None:
        page = _page(
            1,
            1000,
            [
                _line("p1_l1", 0, 50, 100, 100, "HEADER", 0.99),  # excluded
                _line("p1_l2", 0, 500, 100, 600, "BODY", 0.99),  # included
            ],
        )
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert ev.header_band_excluded is True
        assert ev.excluded_line_count == 1
        assert len(ev.included_lines) == 1


class TestSerializationOrder:
    def test_includes_in_page_then_line_order(self) -> None:
        page1 = _page(
            1,
            1000,
            [
                _line("p1_l1", 0, 300, 100, 400, "A", 0.9),
                _line("p1_l2", 0, 500, 100, 600, "B", 0.9),
            ],
        )
        page2 = _page(
            2,
            1000,
            [
                _line("p2_l1", 0, 100, 100, 200, "C", 0.9),
                _line("p2_l2", 0, 800, 100, 900, "D", 0.9),
            ],
        )
        ev = build_body_ocr_evidence(_preprocess([page1, page2]))
        assert [line.raw_text for line in ev.included_lines] == ["A", "B", "C", "D"]
        assert [line.page_index for line in ev.included_lines] == [0, 0, 1, 1]
        assert [line.line_index for line in ev.included_lines] == [0, 1, 0, 1]


class TestNormalizedSearchString:
    def test_concatenates_all_with_single_space_then_normalizes(self) -> None:
        page = _page(
            1,
            1000,
            [
                _line("p1_l1", 0, 300, 100, 400, "Foo BAR", 0.9),
                _line("p1_l2", 0, 500, 100, 600, "BAZ.", 0.9),
            ],
        )
        ev = build_body_ocr_evidence(_preprocess([page]))
        # Joined with " " → "Foo BAR BAZ." → normalize → "foo bar baz"
        assert ev.normalized_search_string == "foo bar baz"


class TestRawTokens:
    def test_whitespace_split(self) -> None:
        page = _page(
            1,
            1000,
            [_line("p1_l1", 0, 500, 100, 600, "  $21:00\tWidget  ", 0.95)],
        )
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert list(ev.included_lines[0].raw_tokens) == ["$21:00", "Widget"]


class TestLaneRobust:
    def test_pps_v3_and_ocr_only_same_result(self) -> None:
        """The build does not inspect blocks/tables; same input shape works for both."""
        # OCR-only shape: blocks empty, raw_ocr_lines populated
        page_ocr_only = _page(1, 1000, [_line("p1_l1", 0, 500, 100, 600, "x", 0.9)])
        # PPStructureV3 shape: blocks present (but the gate ignores them)
        page_pps = dict(page_ocr_only)
        page_pps["blocks"] = [
            {
                "block_id": "p1_b1",
                "block_type": "table",
                "bbox": [0, 500, 100, 600],
                "reading_order": 1,
                "text": "x",
                "confidence": 0.9,
            }
        ]
        ev_ocr_only = build_body_ocr_evidence(_preprocess([page_ocr_only]))
        ev_pps = build_body_ocr_evidence(_preprocess([page_pps]))
        assert ev_ocr_only.normalized_search_string == ev_pps.normalized_search_string
        assert len(ev_ocr_only.included_lines) == len(ev_pps.included_lines)


class TestEmptyAndEdgeCases:
    def test_empty_pages_returns_empty_evidence(self) -> None:
        ev = build_body_ocr_evidence(_preprocess([]))
        assert list(ev.included_lines) == []
        assert ev.excluded_line_count == 0
        assert ev.normalized_search_string == ""
        assert ev.header_band_excluded is False

    def test_zero_height_page_one_lines_fail_closed(self) -> None:
        # Per Sourcery review on PR #45 (2026-05-23): the previous
        # version of this test used height=1000 with no lines, which
        # actually exercised the empty-pages path. This rewrite uses
        # height=0 with one body line to cover the zero-height
        # fail-closed branch in build_body_ocr_evidence: when the page-1
        # threshold cannot be computed, every page-1 line is excluded
        # and header_band_excluded is True.
        page = _page(1, 0, [_line("p1_l1", 10, 100, 200, 130, "body text", 0.97)])
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert list(ev.included_lines) == []
        assert ev.excluded_line_count == 1
        assert ev.header_band_excluded is True

    def test_malformed_page1_bbox_fail_closed(self) -> None:
        # Per Sourcery review on PR #45 (2026-05-23): bbox values that
        # are not a 4-element numeric list (e.g. wrong length, NaN coords)
        # must be excluded from body OCR on page 1 with header_band_excluded
        # set to True — verifies the fail-closed paths in _line_top_y /
        # build_body_ocr_evidence.
        bad_lines = [
            # wrong length
            {"line_id": "p1_l1", "bbox": [10, 100, 200], "text": "trunc", "confidence": 0.95},
            # not a list
            {"line_id": "p1_l2", "bbox": "not-a-list", "text": "wrong-type", "confidence": 0.95},
            # bool coords (numeric-looking but disallowed)
            {"line_id": "p1_l3", "bbox": [True, False, True, False], "text": "bools", "confidence": 0.95},
        ]
        page = _page(1, 1000, bad_lines)
        ev = build_body_ocr_evidence(_preprocess([page]))
        assert list(ev.included_lines) == []
        assert ev.excluded_line_count == 3
        assert ev.header_band_excluded is True
