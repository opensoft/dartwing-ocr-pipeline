"""End-to-end orchestration for the PDF preprocessing slice.

Single-engine per page (PPStructureV3 via `ocr.run_page`) with FR-003,
FR-018, FR-019 defensive checks and FR-020 warning ordering. EngineInitError
(FR-016) is NOT caught here — it propagates to the CLI for hard-fail exit.
"""

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
from ledgerlinc_ocr.preprocessing.warnings import build_warning, sort_warnings

DOCUMENT_ID_RE = re.compile(r"^inv_\d{3}$")

_TEXT_BEARING_BLOCK_TYPES = {"text", "title", "header", "footer"}


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
    silent_empty_page_detected = False

    for pr in rasters:
        page_warnings: list[str] = []
        blocks: list[dict[str, Any]] = []
        page_tables: list[dict[str, Any]] = []
        lines: list[dict[str, Any]] = []

        if isinstance(pr, rasterize.PageRasterFailure):
            page_warnings.append(
                f"page {pr.page_number}: rasterization failed: {pr.error}"
            )
            pages.append(
                {
                    "page_number": pr.page_number,
                    "width": pr.width,
                    "height": pr.height,
                    "rotation_detected": pr.rotation_detected,
                    "blocks": [],
                    "raw_ocr_lines": [],
                }
            )
            warnings_out.extend(page_warnings)
            continue

        # Single V3 call producing both layout + OCR in one pass (FR-007, R-004).
        # EngineInitError raised here propagates to the CLI (FR-016).
        lines, blocks, page_tables, run_warnings = ocr.run_page(
            pr.image, pr.page_number, pr.width, pr.height
        )
        page_warnings.extend(run_warnings)

        # FR-003: silent-empty-layout — lines produced but no blocks.
        if len(lines) > 0 and len(blocks) == 0:
            page_warnings.append(
                build_warning(
                    pr.page_number,
                    "silent_empty_layout",
                    f"OCR produced {len(lines)} lines but layout returned zero blocks",
                )
            )
            silent_empty_page_detected = True

        # FR-019: silent-empty-ocr — blocks produced but no OCR lines, AND at
        # least one block is text-bearing (text/title/header/footer). Figure-
        # and table-only pages legitimately have zero OCR lines.
        text_bearing_blocks = [
            b for b in blocks if b.get("block_type") in _TEXT_BEARING_BLOCK_TYPES
        ]
        if (
            len(blocks) > 0
            and len(lines) == 0
            and len(text_bearing_blocks) > 0
        ):
            page_warnings.append(
                build_warning(
                    pr.page_number,
                    "silent_empty_ocr",
                    f"OCR returned zero lines despite {len(text_bearing_blocks)} text-type blocks",
                )
            )
            silent_empty_page_detected = True

        # FR-018: suspicious-single-block — multiple OCR lines but only one
        # layout region. Warn, but do NOT downgrade status.
        if len(lines) >= 2 and len(blocks) == 1:
            page_warnings.append(
                build_warning(
                    pr.page_number,
                    "suspicious_single_block",
                    f"single block covers {len(lines)} OCR lines",
                )
            )

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
        if lines or blocks:
            pages_with_output += 1

        if invocation.write_page_images:
            img_path = invocation.document_folder / f"page_{pr.page_number}.png"
            pr.image.save(img_path)

    quality = compute_quality(all_lines, max_skew_deg=max_skew)
    ingestion_sources = build_ingestion_sources(
        pages_total=len(pages),
        pages_with_paddleocr_output=pages_with_output,
        silent_empty_page_detected=silent_empty_page_detected,
    )
    if (
        ingestion_sources["paddleocr_vl"]["status"] == "failure"
        and pages_with_output == 0
    ):
        warnings_out.append("ingestion_sources.paddleocr_vl: failure (all pages failed)")

    # FR-020: sort the final warnings array (page-ascending, vocab-lexical within
    # page, page-scoped non-categorized after categorized, aggregate last).
    warnings_out = sort_warnings(warnings_out)

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
