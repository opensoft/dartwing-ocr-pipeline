"""FR-018: a partially failed preprocess run still yields a packet with status preserved."""
from __future__ import annotations

from ledgerlinc_ocr.evidence_packet import assemble_from_folder


def test_partial_failure_preserved(folder_with_preprocess):
    folder = folder_with_preprocess("paddle_failure.json")
    packet = assemble_from_folder(folder)

    paddle = packet["ingestion_sources"]["paddleocr_vl"]
    assert paddle["status"] == "failure"
    assert paddle["enabled"] is True
    assert paddle["payload"] is None

    # Evidence still present even though the source that produced it failed.
    assert packet["document_text"] == "fallback text"
    assert len(packet["pages"]) == 1
