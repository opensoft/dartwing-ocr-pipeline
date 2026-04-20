"""End-to-end orchestration for the PDF preprocessing slice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ledgerlinc_ocr.preprocessing import artifact as artifact_mod
from ledgerlinc_ocr.preprocessing import ocr, rasterize
from ledgerlinc_ocr.preprocessing.errors import InputRejectedError
from ledgerlinc_ocr.preprocessing.ingestion_sources import build_ingestion_sources
from ledgerlinc_ocr.preprocessing.quality import compute_quality
from ledgerlinc_ocr.preprocessing.version import (
    CONTRACT_SET_VERSION,
    DPI,
    build_pipeline_version,
)

DOCUMENT_ID_RE = re.compile(r"^inv_\d{3}$")


@dataclass
class Invocation:
    document_folder: Path
    source_file: str = "source.pdf"
    write_page_images: bool = False
    pipeline_version: str | None = None


def _derive_document_id(folder_name: str) -> str:
    match = re.match(r"^(inv_\d{3})(?:_.*)?$", folder_name)
    if not match:
        raise InputRejectedError(
            f"folder name {folder_name!r} does not match pattern inv_XXX[_<difficulty>]"
        )
    return match.group(1)


def _validate_input(invocation: Invocation) -> Path:
    folder = invocation.document_folder
    if not folder.is_dir():
        raise InputRejectedError(f"document folder does not exist: {folder}")
    pdf_path = folder / invocation.source_file
    if not pdf_path.is_file():
        raise InputRejectedError(f"source file not found: {pdf_path}")
    return pdf_path


def run(invocation: Invocation) -> Path:
    pdf_path = _validate_input(invocation)
    document_id = _derive_document_id(invocation.document_folder.name)
    pipeline_version = invocation.pipeline_version or build_pipeline_version()

    rasters = rasterize.rasterize_pdf(pdf_path, dpi=DPI)
    if not rasters:
        raise InputRejectedError("PDF produced zero rasterized pages")

    pages: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    warnings_out: list[str] = []
    all_lines: list[dict[str, Any]] = []
    max_skew = 0.0
    pages_with_output = 0

    for pr in rasters:
        page_warnings: list[str] = []
        blocks: list[dict[str, Any]] = []
        page_tables: list[dict[str, Any]] = []
        lines: list[dict[str, Any]] = []

        try:
            lines, w_ocr = ocr.run_ocr_lines(pr.image, pr.page_number, pr.width, pr.height)
            page_warnings.extend(w_ocr)
        except Exception as exc:
            page_warnings.append(
                f"page {pr.page_number}: OCR failed: {type(exc).__name__}: {exc}"
            )
            lines = []

        try:
            blocks, page_tables, w_layout = ocr.run_layout(
                pr.image, pr.page_number, pr.width, pr.height
            )
            page_warnings.extend(w_layout)
        except Exception as exc:
            page_warnings.append(
                f"page {pr.page_number}: layout extraction failed: {type(exc).__name__}: {exc}"
            )
            blocks = []
            page_tables = []

        if pr.rotation_snapped:
            page_warnings.append(
                f"page {pr.page_number}: rotation {pr.rotation_original}° normalized to {pr.rotation_detected}°"
            )

        pages.append(
            {
                "page_number": pr.page_number,
                "width": pr.width,
                "height": pr.height,
                "rotation_detected": pr.rotation_detected,
                "blocks": blocks,
                "raw_ocr_lines": lines,
            }
        )
        tables.extend(page_tables)
        warnings_out.extend(page_warnings)
        all_lines.extend(lines)
        if blocks or lines:
            pages_with_output += 1

        if invocation.write_page_images:
            img_path = invocation.document_folder / f"page_{pr.page_number}.png"
            pr.image.save(img_path)

    quality = compute_quality(all_lines, max_skew_deg=max_skew)
    ingestion_sources = build_ingestion_sources(
        pages_total=len(pages), pages_with_paddleocr_output=pages_with_output
    )
    if ingestion_sources["paddleocr_vl"]["status"] == "failure":
        warnings_out.append("ingestion_sources.paddleocr_vl: failure (all pages failed)")

    art = artifact_mod.assemble(
        contract_set_version=CONTRACT_SET_VERSION,
        pipeline_version=pipeline_version,
        document_id=document_id,
        source_file=invocation.source_file,
        pages=pages,
        tables=tables,
        quality=quality,
        ingestion_sources=ingestion_sources,
        warnings=warnings_out,
    )
    out_path = invocation.document_folder / artifact_mod.ARTIFACT_FILENAME
    artifact_mod.validate_and_write(art, out_path)
    return out_path
