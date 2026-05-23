"""T028 / FR-016 / Q4 / Q26 — verdict aggregation tests.

Status mapping (any-fail rule, MI-10/Q4):
- failed       → len(failed_checks) > 0
- passed       → zero failed checks across all rows
- not_applicable → no sidecar
- unevaluable  → sidecar present but input unreadable

Status string is verbatim one of "passed" / "failed" / "not_applicable" /
"unevaluable" — no capitalization, no None (MI-11 / Q26).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.evaluator.semantic_quality import run_semantic_quality_gate
from dartwing_ocr.evaluator.semantic_quality_report import SemanticQualityResult


def _minimal_preprocess(tmp_path: Path) -> Path:
    """Write a minimal schema-valid preprocess_output.json with one body line."""
    obj = {
        "contract_set_version": "1.3.0",
        "pipeline_version": "test",
        "document_id": "doc",
        "source_type": "pdf",
        "source_file": "x.pdf",
        "page_count": 1,
        "pages": [
            {
                "page_number": 1,
                "width": 2550,
                "height": 1000,
                "rotation_detected": 0,
                "blocks": [],
                "raw_ocr_lines": [
                    {
                        "line_id": "p1_l1",
                        "bbox": [0, 500, 100, 600],
                        "text": "Widget body line",
                        "confidence": 0.95,
                    }
                ],
            }
        ],
        "document_text": "",
        "tables": [],
        "quality": {
            "scan_quality": "good",
            "skew_detected": False,
            "noise_level": "low",
        },
        "ingestion_sources": {
            "paddleocr_vl": {"enabled": True, "status": "success"},
            "falcon_ocr": {"enabled": False, "status": "not_implemented"},
            "falcon_perception": {"enabled": False, "status": "not_implemented"},
        },
        "warnings": [],
    }
    path = tmp_path / "preprocess_output.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def _sidecar(tmp_path: Path, body_id: str, rows: list[dict]) -> Path:
    obj = {"document_id": body_id, "rows": rows}
    path = tmp_path / "semantic_table_truth.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


class TestStatusValues:
    def test_status_passed_when_zero_failures(self, tmp_path: Path) -> None:
        pp = _minimal_preprocess(tmp_path)
        sc = _sidecar(
            tmp_path,
            "test_doc",
            [{"row_id": "row-1", "required_row_text_tokens": ["Widget"]}],
        )
        result = run_semantic_quality_gate(pp, sc, folder_basename="test_doc")
        assert result.status == "passed"

    def test_status_failed_when_any_failure(self, tmp_path: Path) -> None:
        pp = _minimal_preprocess(tmp_path)
        sc = _sidecar(
            tmp_path,
            "test_doc",
            [{"row_id": "row-1", "required_row_text_tokens": ["NotInBody"]}],
        )
        result = run_semantic_quality_gate(pp, sc, folder_basename="test_doc")
        assert result.status == "failed"

    def test_status_not_applicable_when_no_sidecar(self, tmp_path: Path) -> None:
        pp = _minimal_preprocess(tmp_path)
        result = run_semantic_quality_gate(pp, sidecar_path=None, folder_basename="test_doc")
        assert result.status == "not_applicable"

    def test_status_unevaluable_when_preprocess_missing(self, tmp_path: Path) -> None:
        sc = _sidecar(
            tmp_path,
            "test_doc",
            [{"row_id": "row-1", "required_row_text_tokens": ["Widget"]}],
        )
        # preprocess_output.json does not exist
        result = run_semantic_quality_gate(
            preprocess_output_path=tmp_path / "preprocess_output.json",
            sidecar_path=sc,
            folder_basename="test_doc",
        )
        assert result.status == "unevaluable"


class TestStatusStringLiterals:
    @pytest.mark.parametrize(
        "status", ["passed", "failed", "not_applicable", "unevaluable"]
    )
    def test_each_status_is_lowercase_snake_case_verbatim(self, status: str) -> None:
        # MI-11 / Q26: these four exact literals; no others.
        assert status == status.lower()
        assert " " not in status

    def test_no_uppercase_variants_ever_emitted(self, tmp_path: Path) -> None:
        pp = _minimal_preprocess(tmp_path)
        sc = _sidecar(
            tmp_path,
            "test_doc",
            [{"row_id": "row-1", "required_row_text_tokens": ["Widget"]}],
        )
        result = run_semantic_quality_gate(pp, sc, folder_basename="test_doc")
        assert result.status in {"passed", "failed", "not_applicable", "unevaluable"}
        assert result.status != "PASSED"
        assert result.status != "Passed"
        assert result.status is not None


class TestReturnType:
    def test_returns_semantic_quality_result(self, tmp_path: Path) -> None:
        pp = _minimal_preprocess(tmp_path)
        sc = _sidecar(
            tmp_path,
            "test_doc",
            [{"row_id": "row-1", "required_row_text_tokens": ["Widget"]}],
        )
        result = run_semantic_quality_gate(pp, sc, folder_basename="test_doc")
        assert isinstance(result, SemanticQualityResult)
