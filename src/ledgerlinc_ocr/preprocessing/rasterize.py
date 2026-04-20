"""Deterministic CPU-only PDF rasterization via pypdfium2 (FR-004, FR-005, FR-006)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image

from ledgerlinc_ocr.preprocessing.errors import InputRejectedError
from ledgerlinc_ocr.preprocessing.version import DPI

ALLOWED_ROTATIONS = (0, 90, 180, 270)

PDF_MAGIC = b"%PDF-"


@dataclass(frozen=True)
class PageRaster:
    page_number: int
    width: int
    height: int
    rotation_detected: int
    rotation_original: int
    rotation_snapped: bool
    image: Image.Image


def _snap_rotation(angle_deg: float) -> tuple[int, bool]:
    normalized = angle_deg % 360
    snapped = min(ALLOWED_ROTATIONS, key=lambda a: min(abs(normalized - a), 360 - abs(normalized - a)))
    changed = int(normalized) != snapped or normalized != float(snapped)
    return snapped, changed


def _check_pdf_magic(pdf_path: Path) -> None:
    try:
        with pdf_path.open("rb") as f:
            header = f.read(8)
    except OSError as exc:
        raise InputRejectedError(f"cannot read PDF bytes: {exc}") from exc
    if not header.startswith(PDF_MAGIC):
        raise InputRejectedError(
            f"file {pdf_path.name} does not start with %PDF- magic — not a PDF"
        )


def open_pdf(pdf_path: Path) -> pdfium.PdfDocument:
    _check_pdf_magic(pdf_path)
    try:
        doc = pdfium.PdfDocument(str(pdf_path))
    except pdfium.PdfiumError as exc:
        message = str(exc).lower()
        if "password" in message or "encrypted" in message:
            raise InputRejectedError(f"encrypted or password-protected PDF: {exc}") from exc
        raise InputRejectedError(f"malformed PDF: {exc}") from exc
    if len(doc) == 0:
        raise InputRejectedError("PDF has zero pages")
    return doc


def rasterize_pdf(pdf_path: Path, dpi: int = DPI) -> list[PageRaster]:
    doc = open_pdf(pdf_path)
    pages: list[PageRaster] = []
    try:
        scale = dpi / 72.0
        for idx in range(len(doc)):
            page = doc[idx]
            try:
                original_rotation = int(page.get_rotation() or 0)
                snapped_rotation, changed = _snap_rotation(original_rotation)
                bitmap = page.render(scale=scale, rotation=snapped_rotation)
                pil_image = bitmap.to_pil().convert("RGB")
                width, height = pil_image.size
                pages.append(
                    PageRaster(
                        page_number=idx + 1,
                        width=int(width),
                        height=int(height),
                        rotation_detected=snapped_rotation,
                        rotation_original=original_rotation,
                        rotation_snapped=changed,
                        image=pil_image,
                    )
                )
            finally:
                page.close()
    finally:
        doc.close()
    return pages
