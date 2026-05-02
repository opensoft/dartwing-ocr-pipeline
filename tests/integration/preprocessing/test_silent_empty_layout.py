"""FR-003 silent-empty-layout: OCR produces lines but layout returns zero blocks.

The stub mimics the pre-remediation V2 failure mode (inv_001 on PubLayNet)
where OCR lines came back but `blocks` collapsed to empty — which today the
new engine must still surface defensively rather than silently accept.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlinc_ocr.preprocessing import ocr, pipeline


def _fake_lines_no_blocks(image, page_number, width, height):
    lines = [
        {"line_id": f"p{page_number}_l1", "bbox": [10, 10, 100, 40], "text": "Invoice 123", "confidence": 0.95},
        {"line_id": f"p{page_number}_l2", "bbox": [10, 50, 120, 80], "text": "Desert Diecutting", "confidence": 0.91},
    ]
    return lines, [], [], []


def test_silent_empty_layout_emits_warning_and_downgrades_status(monkeypatch, us1_workdir: Path):
    monkeypatch.setattr(ocr, "run_page", _fake_lines_no_blocks)
    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    art = json.loads(out.read_text(encoding="utf-8"))

    # FR-003: warning is present with the pinned prefix.
    categorized = [w for w in art["warnings"] if "[silent_empty_layout]" in w]
    assert len(categorized) == 1, art["warnings"]
    assert categorized[0] == (
        "page 1: [silent_empty_layout] OCR produced 2 lines but layout returned zero blocks"
    )

    # FR-003: document-level status downgraded.
    assert art["ingestion_sources"]["paddleocr_vl"]["status"] == "failure"

    # Artifact still validates against the active nullable-confidence contract.
    assert art["contract_set_version"] == "1.2.0"


def test_silent_empty_layout_mixed_page_keeps_healthy_page_blocks(monkeypatch, us1_workdir: Path):
    """Pathological single-page fixture: this test only verifies page_1 path via the stub;
    multi-page ACs are exercised in test_us2_multi_page.py against the real engine."""
    monkeypatch.setattr(ocr, "run_page", _fake_lines_no_blocks)
    out = pipeline.run(pipeline.Invocation(document_folder=us1_workdir))
    art = json.loads(out.read_text(encoding="utf-8"))
    # Exactly one page; no blocks on the page that fired FR-003.
    assert len(art["pages"]) == 1
    assert art["pages"][0]["blocks"] == []
    assert len(art["pages"][0]["raw_ocr_lines"]) == 2
