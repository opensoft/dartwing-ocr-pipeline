"""FR-018 suspicious-single-block: ≥2 OCR lines covered by exactly one layout block.

Warns but does NOT downgrade `ingestion_sources.paddleocr_vl.status`.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlinc_ocr.preprocessing import ocr, pipeline


def _fake_lines_single_block(image, page_number, width, height):
    lines = [
        {"line_id": f"p{page_number}_l1", "bbox": [10, 10, 200, 40], "text": "Acme Corp", "confidence": 0.9},
        {"line_id": f"p{page_number}_l2", "bbox": [10, 50, 200, 80], "text": "123 Main St", "confidence": 0.9},
        {"line_id": f"p{page_number}_l3", "bbox": [10, 90, 200, 120], "text": "Invoice #42", "confidence": 0.9},
    ]
    blocks = [
        {
            "block_id": f"p{page_number}_b1",
            "block_type": "text",
            "bbox": [0, 0, 400, 200],
            "reading_order": 1,
            "text": "",
            "confidence": 0.7,
        },
    ]
    return lines, blocks, [], []


def test_suspicious_single_block_emits_warning_without_downgrading(
    monkeypatch, us1_workdir: Path,
):
    monkeypatch.setattr(ocr, "run_page", _fake_lines_single_block)
    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    art = json.loads(out.read_text(encoding="utf-8"))

    categorized = [w for w in art["warnings"] if "[suspicious_single_block]" in w]
    assert len(categorized) == 1, art["warnings"]
    assert categorized[0] == (
        "page 1: [suspicious_single_block] single block covers 3 OCR lines"
    )

    # FR-018 MUST NOT downgrade status — only FR-003 / FR-019 do.
    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "success"


def test_one_line_one_block_does_not_fire_fr018(monkeypatch, us1_workdir: Path):
    """Trigger requires `len(lines) >= 2`; single line + single block is silent."""
    def _stub(image, page_number, width, height):
        lines = [{"line_id": f"p{page_number}_l1", "bbox": [10, 10, 50, 30], "text": "X", "confidence": 0.9}]
        blocks = [{
            "block_id": f"p{page_number}_b1", "block_type": "text",
            "bbox": [0, 0, 100, 50], "reading_order": 1, "text": "", "confidence": 0.7,
        }]
        return lines, blocks, [], []
    monkeypatch.setattr(ocr, "run_page", _stub)
    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    art = json.loads(out.read_text(encoding="utf-8"))
    assert [w for w in art["warnings"] if "[suspicious_single_block]" in w] == []
