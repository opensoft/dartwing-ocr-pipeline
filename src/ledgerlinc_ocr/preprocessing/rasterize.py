"""Deterministic CPU-only PDF rasterization via pypdfium2 (FR-004, FR-005, FR-005a, FR-006).

Page-at-a-time streaming (FR-005a / research R-011): `rasterize_pdf` is a
generator function. Each `PageRaster | PageRasterFailure` is yielded
independently so that the pipeline consumer can finish OCR/layout work on one
page before the next page is rasterized, bounding peak memory under PaddleOCR
3.5's larger CPU-only model bundle.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from ledgerlinc_ocr.preprocessing.errors import (
    EncryptedPdfError,
    MalformedPdfError,
    NonPdfInputError,
    ZeroPagePdfError,
)
from ledgerlinc_ocr.preprocessing.version import DPI

ALLOWED_ROTATIONS = (0, 90, 180, 270)

PDF_MAGIC = b"%PDF-"

FALLBACK_WIDTH = 1
FALLBACK_HEIGHT = 1
FALLBACK_ROTATION = 0


@dataclass(frozen=True)
class PageRaster:
    page_number: int
    width: int
    height: int
    rotation_detected: int
    rotation_original: int
    rotation_snapped: bool
    image: Image.Image


@dataclass(frozen=True)
class PageRasterFailure:
    """Page where rasterization itself failed; fallback dims per FR-005a."""

    page_number: int
    width: int
    height: int
    rotation_detected: int
    error: str


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
        raise MalformedPdfError(f"cannot read PDF bytes: {exc}") from exc
    if not header.startswith(PDF_MAGIC):
        raise NonPdfInputError(
            f"file {pdf_path.name} does not start with %PDF- magic — not a PDF"
        )


def open_pdf(pdf_path: Path) -> pdfium.PdfDocument:
    _check_pdf_magic(pdf_path)
    try:
        doc = pdfium.PdfDocument(str(pdf_path))
    except pdfium.PdfiumError as exc:
        message = str(exc).lower()
        if "password" in message or "encrypted" in message:
            raise EncryptedPdfError(f"encrypted or password-protected PDF: {exc}") from exc
        raise MalformedPdfError(f"malformed PDF: {exc}") from exc
    try:
        page_count = len(doc)
    except Exception as exc:
        doc.close()
        raise MalformedPdfError(f"cannot determine page count: {exc}") from exc
    if page_count == 0:
        doc.close()
        raise ZeroPagePdfError("PDF has zero pages")
    return doc


def _metadata_fallback_dims(page, dpi: int = DPI) -> tuple[int, int]:
    """FR-005a: point dims × DPI / 72, rounded, minimum 1 (schema constraint).

    Feature 018 (T008): the `dpi` parameter is now threaded from the
    caller (`rasterize_pdf`) so that `--raster-profile=reduced-v1` runs
    with page-level rasterization failures produce fallback dims
    consistent with the resolved RasterProfile's DPI (rather than always
    falling back to the module-level `DPI = 300`). Default preserves
    legacy behavior for callers that don't yet pass dpi explicitly.
    """
    try:
        width_pt, height_pt = page.get_size()
        w = max(FALLBACK_WIDTH, round(float(width_pt) * dpi / 72.0))
        h = max(FALLBACK_HEIGHT, round(float(height_pt) * dpi / 72.0))
        return int(w), int(h)
    except Exception:
        return FALLBACK_WIDTH, FALLBACK_HEIGHT


def rasterize_pdf(
    pdf_path: Path, dpi: int = DPI
) -> Iterator[PageRaster | PageRasterFailure]:
    """Yield one rasterized page at a time (FR-005a / R-011).

    The consumer (`pipeline.run`) is expected to fully process and release
    each page before iterating to the next — that is the entire point of the
    streaming contract. A zero-page PDF raises `ZeroPagePdfError` inside
    `open_pdf` on the first `next()`, before any page is yielded.

    Feature 018 (T008 / R-018.2 / contracts/cli-contract.md §1): the
    `dpi` parameter is driven by the resolved
    `RasterProfile.dpi` from `preprocessing/raster_profiles.py` on the
    GPU lane (default `legacy` = 300; `reduced-v1` = 200). The CPU lane
    keeps the module-level `DPI = 300` default per FR-015 / I-018.2.
    """
    doc = open_pdf(pdf_path)
    try:
        scale = dpi / 72.0
        for idx in range(len(doc)):
            page_number = idx + 1
            try:
                page = doc[idx]
            except Exception as exc:
                yield PageRasterFailure(
                    page_number=page_number,
                    width=FALLBACK_WIDTH,
                    height=FALLBACK_HEIGHT,
                    rotation_detected=FALLBACK_ROTATION,
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue
            try:
                try:
                    original_rotation = int(page.get_rotation() or 0)
                    snapped_rotation, changed = _snap_rotation(original_rotation)
                    bitmap = page.render(scale=scale, rotation=snapped_rotation)
                    pil_image = bitmap.to_pil().convert("RGB")
                    width, height = pil_image.size
                    yield PageRaster(
                        page_number=page_number,
                        width=int(width),
                        height=int(height),
                        rotation_detected=snapped_rotation,
                        rotation_original=original_rotation,
                        rotation_snapped=changed,
                        image=pil_image,
                    )
                except Exception as exc:
                    fb_w, fb_h = _metadata_fallback_dims(page, dpi=dpi)
                    yield PageRasterFailure(
                        page_number=page_number,
                        width=fb_w,
                        height=fb_h,
                        rotation_detected=FALLBACK_ROTATION,
                        error=f"{type(exc).__name__}: {exc}",
                    )
            finally:
                page.close()
    finally:
        doc.close()
