"""Unit tests for deterministic JSON writer (Phase 2 T011)."""

from pathlib import Path

import pytest

from ledgerlinc_ocr.assembler.write import FINAL_KEY_ORDER, write_final_payload


def _sample_payload() -> dict:
    return {
        "trace": {"source_file": "source.pdf"},
        "contract_set_version": "1.0.0",
        "pipeline_version": "009-final-payload@0.1.0",
        "document_id": "inv_001",
        "processed_at": "2026-04-21T12:00:00Z",
        "document_type": "invoice",
        "vendor_candidate": {"company_name": {"value": "X"}},
        "review_status": {"manual_review_required": False, "review_reason": None},
        "quality_summary": {"overall_vendor_confidence": 0.5},
    }


def test_byte_identical_output_across_calls(tmp_path: Path):
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    payload = _sample_payload()
    write_final_payload(p1, payload)
    write_final_payload(p2, payload)
    assert p1.read_bytes() == p2.read_bytes()


def test_output_ends_with_trailing_newline(tmp_path: Path):
    p = tmp_path / "out.json"
    write_final_payload(p, _sample_payload())
    assert p.read_bytes().endswith(b"\n")


def test_top_level_keys_emitted_in_schema_order(tmp_path: Path):
    p = tmp_path / "out.json"
    write_final_payload(p, _sample_payload())
    text = p.read_text(encoding="utf-8")
    positions = [text.index(f'"{k}"') for k in FINAL_KEY_ORDER]
    assert positions == sorted(positions)


def test_utf8_non_ascii_preserved(tmp_path: Path):
    p = tmp_path / "out.json"
    payload = _sample_payload()
    payload["vendor_candidate"]["company_name"]["value"] = "Café Münster"
    write_final_payload(p, payload)
    assert "Café Münster" in p.read_text(encoding="utf-8")
