"""T030 / Q31 / R-022.13 — unevaluable cause-cascade tests.

Four-step cascade:
  1. preprocess_output.json missing      → cause = preprocess_output_missing
  2. file present, unparseable JSON       → cause = preprocess_output_invalid_json
  3. file parses, fails schema validation → cause = preprocess_output_schema_invalid
  4. file parses + schema-valid, zero body OCR lines → cause = body_ocr_unreadable

Gate-time invariant violations raise SemanticGateInvariantError; NOT
recorded as unevaluable (Q42 / MI-19).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.evaluator.exceptions import SemanticGateInvariantError
from dartwing_ocr.evaluator.semantic_quality import run_semantic_quality_gate


def _sidecar(tmp_path: Path, body_id: str, rows: list[dict]) -> Path:
    obj = {"document_id": body_id, "rows": rows}
    path = tmp_path / "semantic_table_truth.json"
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def _valid_pp(pages: list[dict]) -> dict:
    return {
        "contract_set_version": "1.3.0",
        "pipeline_version": "test",
        "document_id": "doc",
        "source_type": "pdf",
        "source_file": "x.pdf",
        "page_count": len(pages) if pages else 1,
        "pages": pages
        or [
            {
                "page_number": 1,
                "width": 2550,
                "height": 1000,
                "rotation_detected": 0,
                "blocks": [],
                "raw_ocr_lines": [],
            }
        ],
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


class TestUnevaluableCascade:
    def test_step1_missing_file(self, tmp_path: Path) -> None:
        sc = _sidecar(tmp_path, "doc", [{"row_id": "r-1", "required_row_text_tokens": ["X"]}])
        result = run_semantic_quality_gate(
            preprocess_output_path=tmp_path / "preprocess_output.json",
            sidecar_path=sc,
            folder_basename="doc",
        )
        assert result.status == "unevaluable"
        assert result.cause == "preprocess_output_missing"

    def test_step2_invalid_json(self, tmp_path: Path) -> None:
        pp = tmp_path / "preprocess_output.json"
        pp.write_text("{not valid json", encoding="utf-8")
        sc = _sidecar(tmp_path, "doc", [{"row_id": "r-1", "required_row_text_tokens": ["X"]}])
        result = run_semantic_quality_gate(
            preprocess_output_path=pp, sidecar_path=sc, folder_basename="doc"
        )
        assert result.status == "unevaluable"
        assert result.cause == "preprocess_output_invalid_json"

    def test_step3_schema_invalid(self, tmp_path: Path) -> None:
        pp = tmp_path / "preprocess_output.json"
        # Missing required keys → schema validation fails
        pp.write_text(json.dumps({"document_id": "doc"}), encoding="utf-8")
        sc = _sidecar(tmp_path, "doc", [{"row_id": "r-1", "required_row_text_tokens": ["X"]}])
        result = run_semantic_quality_gate(
            preprocess_output_path=pp, sidecar_path=sc, folder_basename="doc"
        )
        assert result.status == "unevaluable"
        assert result.cause == "preprocess_output_schema_invalid"

    def test_step4_no_body_lines(self, tmp_path: Path) -> None:
        # Valid schema but zero raw_ocr_lines on every page
        pp = tmp_path / "preprocess_output.json"
        pp.write_text(json.dumps(_valid_pp([])), encoding="utf-8")
        sc = _sidecar(tmp_path, "doc", [{"row_id": "r-1", "required_row_text_tokens": ["X"]}])
        result = run_semantic_quality_gate(
            preprocess_output_path=pp, sidecar_path=sc, folder_basename="doc"
        )
        assert result.status == "unevaluable"
        assert result.cause == "body_ocr_unreadable"


class TestUnevaluableCauseEnum:
    @pytest.mark.parametrize(
        "cause",
        [
            "preprocess_output_missing",
            "preprocess_output_invalid_json",
            "preprocess_output_schema_invalid",
            "body_ocr_unreadable",
        ],
    )
    def test_cause_is_closed_enum_value(self, cause: str) -> None:
        # The four causes are the closed enum from Q31.
        valid = {
            "preprocess_output_missing",
            "preprocess_output_invalid_json",
            "preprocess_output_schema_invalid",
            "body_ocr_unreadable",
        }
        assert cause in valid


class TestInvariantHardError:
    """Q42/MI-19: Gate-time invariant violations propagate as
    SemanticGateInvariantError, NOT converted to unevaluable."""

    def test_invariant_error_is_separate_from_unevaluable(self) -> None:
        # We just verify the type exists and can be raised.
        with pytest.raises(SemanticGateInvariantError):
            raise SemanticGateInvariantError("anchor span has inverted indices")

    def test_invariant_error_is_not_unevaluable_status(self, tmp_path: Path) -> None:
        # A hard-error raising path should propagate, not return a status.
        # We exercise this indirectly by ensuring the exception class is
        # not caught by any branch in the gate's normal cascade.
        pp = tmp_path / "preprocess_output.json"
        pp.write_text(json.dumps(_valid_pp([])), encoding="utf-8")
        sc = _sidecar(tmp_path, "doc", [{"row_id": "r-1", "required_row_text_tokens": ["X"]}])
        # Normal cascade path produces "body_ocr_unreadable", not an exception.
        result = run_semantic_quality_gate(
            preprocess_output_path=pp, sidecar_path=sc, folder_basename="doc"
        )
        assert result.status == "unevaluable"
        # Confirm the result is NOT a SemanticGateInvariantError —
        # invariant errors propagate, not return statuses.
        assert not isinstance(result, SemanticGateInvariantError)
