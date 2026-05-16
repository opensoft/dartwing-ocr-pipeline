"""US1 AC#4 + SC-009: ordered hints with full source-reference integrity."""
from __future__ import annotations

import pytest

from dartwing_ocr.evidence_packet import assemble_from_folder

_HINT_CATEGORIES = ("emails", "websites", "phones", "tax_ids")


def _all_hints(signals):
    for category in _HINT_CATEGORIES:
        for hit in signals[category]:
            yield category, hit


@pytest.mark.parametrize("fixture", ["with_regex_hits.json", "multi_match.json"])
def test_ac4_ordered_hints_with_source_refs(folder_with_preprocess, fixture):
    folder = folder_with_preprocess(fixture)
    packet = assemble_from_folder(folder)
    document_text = packet["document_text"]
    signals = packet["candidate_vendor_signals"]

    assert signals["company_name"] is None
    assert signals["addresses"] == []

    for category in _HINT_CATEGORIES:
        offsets = [h["document_text_offset"] for h in signals[category]]
        assert offsets == sorted(offsets), f"{category} not in ascending offset order"

    for _, hit in _all_hints(signals):
        start = hit["document_text_offset"]
        length = hit["document_text_length"]
        assert document_text[start : start + length] == hit["value"]
        assert hit["page_index"] is not None
        assert hit["block_index"] is not None
        assert hit["line_index"] is not None
        assert hit["provenance"] == "unverified"


def test_multi_match_preserves_duplicates(folder_with_preprocess):
    folder = folder_with_preprocess("multi_match.json")
    packet = assemble_from_folder(folder)
    emails = [h["value"] for h in packet["candidate_vendor_signals"]["emails"]]
    assert emails.count("orders@example.com") == 2
