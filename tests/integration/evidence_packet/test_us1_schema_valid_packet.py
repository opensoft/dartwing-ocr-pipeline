"""US1 AC#1: the packet faithfully preserves preprocess fields."""
from __future__ import annotations

import json

from dartwing_ocr.evidence_packet import assemble_from_folder
from dartwing_ocr.evidence_packet.schema import validate_packet


def test_ac1_passthrough_is_faithful(folder_with_preprocess):
    folder = folder_with_preprocess("minimal_valid.json")
    packet = assemble_from_folder(folder)
    validate_packet(packet)

    preprocess = json.loads((folder / "preprocess_output.json").read_text())

    assert packet["page_count"] == preprocess["page_count"]
    assert packet["source_file"] == preprocess["source_file"]
    assert packet["document_id"] == preprocess["document_id"]
    assert packet["document_text"] == preprocess["document_text"]
    assert packet["tables"] == preprocess["tables"]

    for in_page, out_page in zip(preprocess["pages"], packet["pages"]):
        assert out_page == in_page

    pre_ids = [b["block_id"] for p in preprocess["pages"] for b in p["blocks"]]
    assert packet["reading_order"] == pre_ids
