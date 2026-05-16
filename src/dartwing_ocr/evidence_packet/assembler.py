"""Evidence-packet assembler: input dict → validated packet dict.

Does no filesystem I/O. That is ``__init__.assemble_from_folder``'s job.
"""
from __future__ import annotations

from typing import Any

from dartwing_ocr.evidence_packet import schema as _schema
from dartwing_ocr.evidence_packet.sections.candidate_signals import (
    build_candidate_signals,
)
from dartwing_ocr.evidence_packet.sections.perceptual import (
    build_perceptual_observations,
)
from dartwing_ocr.evidence_packet.sections.structural import build_structural_section
from dartwing_ocr.evidence_packet.sections.tables import build_tables_section
from dartwing_ocr.evidence_packet.sections.trijunction import build_ingestion_sources
from dartwing_ocr.evidence_packet.version import CONTRACT_SET_VERSION


def assemble_from_preprocess(
    preprocess_output: dict[str, Any],
    *,
    document_id: str | None = None,
) -> dict[str, Any]:
    _schema.validate_preprocess_input(preprocess_output)

    structural, spans = build_structural_section(preprocess_output)
    tables = build_tables_section(preprocess_output)
    ingestion_sources = build_ingestion_sources(preprocess_output)
    perceptual = build_perceptual_observations(preprocess_output)
    candidate_signals = build_candidate_signals(
        preprocess_output, structural["document_text"], spans
    )

    doc_id = document_id if document_id is not None else preprocess_output["document_id"]

    packet: dict[str, Any] = {
        "contract_set_version": CONTRACT_SET_VERSION,
        "document_id": doc_id,
        "source_file": preprocess_output["source_file"],
        "page_count": preprocess_output["page_count"],
        "pages": structural["pages"],
        "reading_order": structural["reading_order"],
        "document_text": structural["document_text"],
        "tables": tables,
        "ingestion_sources": ingestion_sources,
        "perceptual_observations": perceptual,
        "candidate_vendor_signals": candidate_signals,
    }

    _schema.validate_packet(packet)
    return packet
