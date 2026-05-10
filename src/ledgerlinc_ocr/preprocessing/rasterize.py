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
from typing import Any

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


def snap_rotation(angle_deg: float) -> tuple[int, bool]:
    """Snap a rotation angle to the closest member of ALLOWED_ROTATIONS.

    Returns ``(snapped_angle, changed)`` where ``changed`` is True iff
    the input did not exactly match an allowed rotation. Promoted from
    private (`_snap_rotation`) to public for cross-module use by
    `preprocessing/pipeline.py::_run_region_first_path` (feature 018 /
    M4 fix — region-first path needs the same snapping logic on its
    synthetic PageRaster).
    """
    normalized = angle_deg % 360
    snapped = min(ALLOWED_ROTATIONS, key=lambda a: min(abs(normalized - a), 360 - abs(normalized - a)))
    changed = int(normalized) != snapped or normalized != float(snapped)
    return snapped, changed


# Backwards-compat alias for any callers that still reference the
# private name (none in-tree as of feature 018; the alias exists only
# to avoid a hard breakage if a downstream feature picks up the old
# name from the git history).
_snap_rotation = snap_rotation


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


def rasterize_page_band(
    pdf_path: Path,
    page_index: int,
    band_bbox_pt: Any,
    dpi: int = DPI,
) -> tuple[Image.Image, tuple[int, int]]:
    """Feature 018 (T017 / R-018.5 / R-018.15): rasterize ONLY the
    targeted band of a single PDF page, returning the cropped PIL Image
    plus the crop's top-left offset in pixel coordinates.

    Used only by the `header-first-v1` region strategy. The orchestrator
    in `preprocessing/pipeline.py` calls this once per document (page 1
    only — pages 2..N are skipped entirely per Clarifications Q2 and
    R-018.6) when `region_strategy_id == "header-first-v1"`.

    `band_bbox_pt` is a `region_strategies.BBox` in TOP-LEFT-ORIGIN PDF
    point coordinates. For `header-first-v1` (R-018.5):
        BBox(x0_pt=0, y0_pt=0, x1_pt=width_pt, y1_pt=0.30 * height_pt)

    `pypdfium2.PdfPage.render(crop=...)` accepts a `(left, bottom, right,
    top)` 4-tuple in BOTTOM-LEFT-ORIGIN PDF native coordinates,
    interpreted as "amount to remove from each edge". For top 30% of
    height (top-left-origin), we need to remove 70% of height from the
    BOTTOM in PDF native (so the visual top survives after pypdfium2's
    render flip).

    Returns `(cropped_image, (offset_x_px, offset_y_px))`. For
    header-first-v1 the offset is `(0, 0)` because the crop keeps the
    visual top-left corner. The orchestrator uses the offset to
    translate PaddleOCR's crop-relative bboxes back to full-page pixel
    coordinates via `region_strategies.translate_bbox` (R-018.15).

    Coordinate convention: `band_bbox_pt` is interpreted in
    top-left-origin PDF-point space. The y-axis flip required by
    pypdfium2's bottom-left-origin `crop=` argument is performed below.
    The header-first crop targets the visual TOP of the page (logo +
    company-name area) — see `tests/integration/preprocessing/`
    coverage that asserts this for known fixtures.
    """
    doc = open_pdf(pdf_path)
    try:
        page = doc[page_index]
        try:
            width_pt, height_pt = page.get_size()
            # Convert top-left-origin BBox → bottom-left-origin pypdfium2
            # crop "amount to remove" tuple. For
            # BBox(x0_pt=0, y0_pt=0, x1_pt=width_pt, y1_pt=h_band):
            #   left=0, right=0 (keep full width)
            #   top=0 (don't remove from PDF-native top, which is the
            #     visual top after pypdfium2's render flip)
            #   bottom=height_pt - h_band (remove the PDF-native bottom
            #     region, which is the visual bottom we don't want)
            crop_left = float(band_bbox_pt.x0_pt)
            crop_right = float(width_pt) - float(band_bbox_pt.x1_pt)
            crop_top = float(band_bbox_pt.y0_pt)
            crop_bottom = float(height_pt) - float(band_bbox_pt.y1_pt)
            scale = dpi / 72.0
            original_rotation = int(page.get_rotation() or 0)
            snapped_rotation, _changed = snap_rotation(original_rotation)
            bitmap = page.render(
                scale=scale,
                rotation=snapped_rotation,
                crop=(crop_left, crop_bottom, crop_right, crop_top),
            )
            crop_image = bitmap.to_pil().convert("RGB")
            # The crop offset relative to the FULL-PAGE rendered image
            # is (x0_px, y0_px) in top-left-origin pixel coordinates.
            # For header-first-v1's BBox(0, 0, width_pt, 0.30 * h_pt)
            # this is (0, 0) — the crop kept the top-left corner.
            offset_x_px = int(round(float(band_bbox_pt.x0_pt) * scale))
            offset_y_px = int(round(float(band_bbox_pt.y0_pt) * scale))
            return crop_image, (offset_x_px, offset_y_px)
        finally:
            page.close()
    finally:
        doc.close()


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
                    snapped_rotation, changed = snap_rotation(original_rotation)
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
