"""Candidate vendor signals: regex hints + null company_name + empty addresses."""
from __future__ import annotations

from typing import Any

from ledgerlinc_ocr.evidence_packet.errors import PacketAssemblyError
from ledgerlinc_ocr.evidence_packet.offset_mapping import BlockSpan, reverse_map
from ledgerlinc_ocr.evidence_packet.regex_hints import find_hints


def _build_hint(
    value: str,
    start: int,
    end: int,
    document_text: str,
    spans: list[BlockSpan],
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    length = end - start
    if document_text[start:end] != value:
        raise PacketAssemblyError(
            f"regex hint offset integrity violated: document_text[{start}:{end}] "
            f"!= {value!r}"
        )
    page_idx, block_idx, line_idx = reverse_map(start, spans, pages)
    return {
        "value": value,
        "document_text_offset": start,
        "document_text_length": length,
        "page_index": page_idx,
        "block_index": block_idx,
        "line_index": line_idx,
        "provenance": "unverified",
    }


def build_candidate_signals(
    preprocess_output: dict[str, Any],
    document_text: str,
    spans: list[BlockSpan],
) -> dict[str, Any]:
    hits = find_hints(document_text)
    pages = preprocess_output["pages"]

    def _hints(category: str) -> list[dict[str, Any]]:
        return [
            _build_hint(value, start, end, document_text, spans, pages)
            for (value, start, end) in hits[category]
        ]

    return {
        "company_name": None,
        "addresses": [],
        "emails": _hints("emails"),
        "websites": _hints("websites"),
        "phones": _hints("phones"),
        "tax_ids": _hints("tax_ids"),
    }
