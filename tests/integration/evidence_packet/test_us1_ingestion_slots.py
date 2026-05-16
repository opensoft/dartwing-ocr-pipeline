"""US1 AC#3: all three Trijunction slots present; payload null on failure / not_implemented."""
from __future__ import annotations

from dartwing_ocr.evidence_packet import assemble_from_folder


def test_ac3_slot_preservation(folder_with_preprocess):
    folder = folder_with_preprocess("all_sources_not_implemented.json")
    packet = assemble_from_folder(folder)

    sources = packet["ingestion_sources"]
    assert set(sources.keys()) == {"paddleocr_vl", "falcon_ocr", "falcon_perception"}

    for slot_name, slot in sources.items():
        assert set(slot.keys()) == {"enabled", "status", "payload"}, slot_name
        if slot["status"] in {"failure", "not_implemented"}:
            assert slot["payload"] is None, slot_name
