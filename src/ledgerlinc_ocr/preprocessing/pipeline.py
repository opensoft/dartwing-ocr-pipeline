"""End-to-end orchestration for the PDF preprocessing slice.

Single-engine per page (PPStructureV3 via `ocr.run_page`) with FR-003,
FR-018, FR-019 defensive checks and FR-020 warning ordering. EngineInitError
(FR-016) is NOT caught here — it propagates to the CLI for hard-fail exit.

Feature 015 (T016 / R-015.4): `run()` accepts an optional `stage_timing`
parameter (`pipeline.timing.StageTiming`). When provided, the rasterize
loop and artifact-write call are wrapped in `measure_phase` context
managers so the caller can read per-phase seconds (`rasterization`,
`artifact_write`) plus `total_ns` (via `measure_total`). The single-doc
CLI threads its own StageTiming in; the warm-corpus runner passes
`result.timings.stages[Stage.PREPROCESS]` so corpus_run.py can drain
the same channel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

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
from ledgerlinc_ocr.pipeline.timing import StageTiming, measure_phase, measure_total

# Feature 014 / VT-003: `preflight` is imported lazily inside the GPU
# code path (see `_invoke_gpu_gate` below). Module-level import would
# break collection for unrelated tests when `preflight.py` is
# temporarily unavailable (e.g., during the conftest defensive-path
# verification in T035). The CPU path never references preflight.

DOCUMENT_ID_RE = re.compile(r"^inv_\d{3}(?:_(easy|medium|hard|missing_name))?$")

_TEXT_BEARING_BLOCK_TYPES = {"text", "title", "header", "footer"}


@dataclass
class Invocation:
    document_folder: Path
    source_file: str = "source.pdf"
    write_page_images: bool = False
    pipeline_version: str | None = None
    # Feature 014 (T021): preprocess lane resolved from --preprocess-profile.
    # "cpu" (default) or "gpu0" (or "gpu<N>" for non-zero device indices,
    # reserved for future multi-GPU work). The lane is threaded into
    # build_pipeline_version() and ocr.run_page() per FR-016.
    preprocess_lane: str = "cpu"


def _derive_document_id(folder_name: str) -> str:
    if not DOCUMENT_ID_RE.match(folder_name):
        raise InputRejectedError(
            f"folder name {folder_name!r} does not match pattern "
            f"inv_XXX or inv_XXX_<difficulty>"
        )
    return folder_name


def _validate_input(invocation: Invocation) -> Path:
    folder = invocation.document_folder
    if not folder.is_dir():
        raise InputRejectedError(f"document folder does not exist: {folder}")
    pdf_path = folder / invocation.source_file
    if not pdf_path.is_file():
        raise InputRejectedError(f"source file not found: {pdf_path}")
    return pdf_path


def _resolve_lane_to_device(lane: str) -> str:
    """Map a preprocess lane string ('cpu' or 'gpu<N>') to the
    PPStructureV3 `device` argument."""
    if lane == "cpu":
        return "cpu"
    if lane.startswith("gpu") and lane[3:].isdigit():
        return f"gpu:{lane[3:]}"
    raise ValueError(f"unrecognized preprocess lane: {lane!r}")


def run(invocation: Invocation, *, stage_timing: Optional[StageTiming] = None) -> Path:
    """Execute the preprocessing pipeline for one document.

    Feature 015 (T016 / R-015.4): when `stage_timing` is provided (a
    `pipeline.timing.StageTiming` instance), `run()` records the
    `rasterization` and `artifact_write` phases via `measure_phase`,
    and the entire body via `measure_total`. The caller (single-doc CLI
    or warm-corpus Runner) then reads `stage_timing.phases_ns` and
    `stage_timing.total_ns` to assemble the run_summary `phase_timings`
    block. When `stage_timing` is None, an internal StageTiming is
    constructed locally and discarded — preserving exact previous
    behavior for callers that have not adopted the new shape.
    """
    if stage_timing is None:
        stage_timing = StageTiming(stage="preprocess")

    with measure_total(stage_timing):
        return _run_inner(invocation, stage_timing)


def _run_inner(invocation: Invocation, stage_timing: StageTiming) -> Path:
    # Feature 014 (T021 / FR-009): on GPU lane, run the inline preflight
    # gate BEFORE any artifact write or input parsing. This ensures the
    # fail-fast error names the selected profile and FR-001 state even
    # if the document folder is also broken — GPU readiness is a
    # process-level prerequisite, not a per-document one. ensure_gpu_ready
    # is process-cached per Q2 — second and subsequent calls within the
    # same process short-circuit on the cached PPSTRUCTUREV3_INIT_SUCCEEDED
    # readout.
    if invocation.preprocess_lane != "cpu":
        # Lazy import so the CPU path stays decoupled from preflight.
        from ledgerlinc_ocr.preprocessing.preflight import (
            ensure_gpu_ready as _ensure_gpu_ready,
        )

        _ensure_gpu_ready()

    pdf_path = _validate_input(invocation)
    document_id = _derive_document_id(invocation.document_folder.name)

    pipeline_version = invocation.pipeline_version or build_pipeline_version(
        lane_segment=invocation.preprocess_lane,
    )

    # rasterize.rasterize_pdf is a page-at-a-time generator (FR-005a / R-011).
    # ZeroPagePdfError is raised inside open_pdf() on the first next() iteration,
    # so no separate "not rasters" guard is needed.
    # Feature 015 (T016): wrap the rasterize+per-page-OCR loop in
    # `measure_phase("rasterization")`. The per-page GPU inference time is
    # recorded into `ocr._GPU_INFERENCE_NS_BY_PAGE` separately and surfaces
    # via `take_gpu_inference_per_page()` as the run_summary
    # `per_page_inference` array — it is intentionally NOT subtracted from
    # `rasterization` here; the two phases are measured along different
    # axes and the consumer may overlap them.
    rasters = rasterize.rasterize_pdf(pdf_path, dpi=DPI)

    pages: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    warnings_out: list[str] = []
    all_lines: list[dict[str, Any]] = []
    max_skew = 0.0
    pages_with_output = 0
    silent_empty_page_detected = False

    # Manual phase timer (instead of `measure_phase` context manager) so the
    # large for-loop body doesn't need to be indented. Same semantics: the
    # delta is added to `stage_timing.phases_ns["rasterization"]` after the
    # loop completes. measure_phase's `finally` semantics are not needed
    # here because run-loop exceptions are caught inside the loop and
    # turned into per-page warnings; no exception escapes the for body.
    import time as _time
    _rasterize_start_ns = _time.monotonic_ns()
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
        # Feature 014 (T021): pass the resolved device; CPU lane → "cpu",
        # GPU lane → "gpu:0" (or "gpu:N" per CF4).
        lines, blocks, page_tables, run_warnings = ocr.run_page(
            pr.image, pr.page_number, pr.width, pr.height,
            device=_resolve_lane_to_device(invocation.preprocess_lane),
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

        # FR-005a / R-011: release the page image before the next page is
        # rasterized. The page-owned `lines`, `blocks`, `page_tables`, and
        # warnings have already been copied into document-level accumulators.
        try:
            pr.image.close()
        except Exception:
            pass

    # Feature 015 (T016): close the rasterization-phase timer.
    stage_timing.add_phase(
        "rasterization", _time.monotonic_ns() - _rasterize_start_ns
    )

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
    # Feature 015 (T016): time the artifact validate+write as its own phase.
    with measure_phase(stage_timing, "artifact_write"):
        artifact_mod.validate_and_write(art, out_path)
    return out_path
