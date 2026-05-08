"""End-to-end orchestration for the PDF preprocessing slice.

Single-engine per page (PPStructureV3 via `ocr.run_page`) with FR-003,
FR-018, FR-019 defensive checks and FR-020 warning ordering. EngineInitError
(FR-016) is NOT caught here — it propagates to the CLI for hard-fail exit.

Feature 015 (T016 / R-015.4): `run()` accepts an optional `stage_timing`
parameter (`pipeline.timing.StageTiming`). When provided, the rasterize
loop and the artifact-write call are wrapped in `measure_phase` context
managers so the caller can read per-phase seconds (`rasterization`,
`artifact_write`) off `stage_timing.phases_ns`. The caller owns
`measure_total` — when `stage_timing` is passed in, `run()` does NOT
wrap the body in `measure_total` (otherwise the warm-corpus Runner,
which already wraps the same StageTiming in `measure_total`, would
double-count `total_ns`). Only when `stage_timing` is None does `run()`
construct a local one and wrap it in `measure_total`. The single-doc
CLI manages its own `measure_total`; the warm-corpus Runner does so via
`pipeline.timing.measure_total` around each stage_callable invocation.
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
    # Feature 016 (T006 / FR-001 / FR-002 / FR-010): the resolved warmup
    # opt-in boolean. Off by default. When True AND `preprocess_lane` is a
    # GPU lane, `_run_inner` invokes `preprocessing.warmup.run_warmup` once
    # per process between engine adoption and the rasterization phase. CPU
    # and stub paths ignore this flag (the CLI emits the FR-010 warn-and-
    # proceed line at activation-detection time, not here).
    warmup: bool = False


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

    Feature 015 (T016 / R-015.4): when `stage_timing` is provided,
    `run()` records the `rasterization` and `artifact_write` phases via
    `measure_phase`. The caller owns `measure_total` so warm-corpus
    Runner — which already wraps the same StageTiming in
    `measure_total` — does not double-count `total_ns`. When
    `stage_timing` is None, a local one is constructed and `run()`
    wraps the body in `measure_total` itself.
    """
    if stage_timing is None:
        local_timing = StageTiming(stage="preprocess")
        with measure_total(local_timing):
            return _run_inner(invocation, local_timing)
    return _run_inner(invocation, stage_timing)


def _build_failed_page_dict(pr: rasterize.PageRasterFailure) -> dict[str, Any]:
    return {
        "page_number": pr.page_number,
        "width": pr.width,
        "height": pr.height,
        "rotation_detected": pr.rotation_detected,
        "blocks": [],
        "raw_ocr_lines": [],
    }


@dataclass
class _PageResult:
    page_dict: dict[str, Any]
    lines: list[dict[str, Any]]
    blocks: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    warnings: list[str]
    silent_empty: bool


def _build_page_warnings(
    pr: Any, lines: list[dict[str, Any]], blocks: list[dict[str, Any]]
) -> tuple[list[str], bool]:
    """Compute defensive warnings for a successful page (FR-003, FR-018,
    FR-019, plus rotation-normalized note). Returns (warnings, silent_empty).
    """
    page_warnings: list[str] = []
    silent_empty = False

    # FR-003: silent-empty-layout — lines produced but no blocks.
    if len(lines) > 0 and len(blocks) == 0:
        page_warnings.append(
            build_warning(
                pr.page_number,
                "silent_empty_layout",
                f"OCR produced {len(lines)} lines but layout returned zero blocks",
            )
        )
        silent_empty = True

    # FR-019: silent-empty-ocr — blocks produced but no OCR lines, AND at
    # least one block is text-bearing. Figure- and table-only pages
    # legitimately have zero OCR lines.
    text_bearing_blocks = [
        b for b in blocks if b.get("block_type") in _TEXT_BEARING_BLOCK_TYPES
    ]
    if len(blocks) > 0 and len(lines) == 0 and len(text_bearing_blocks) > 0:
        page_warnings.append(
            build_warning(
                pr.page_number,
                "silent_empty_ocr",
                f"OCR returned zero lines despite {len(text_bearing_blocks)} text-type blocks",
            )
        )
        silent_empty = True

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

    return page_warnings, silent_empty


def _process_page(pr: Any, invocation: Invocation) -> _PageResult:
    """Run OCR on one rasterized page and assemble the per-page result.

    Handles the FR-003 / FR-018 / FR-019 defensive checks, page-image
    cleanup (FR-005a / R-011), and the optional `write_page_images`
    debug write.
    """
    if isinstance(pr, rasterize.PageRasterFailure):
        return _PageResult(
            page_dict=_build_failed_page_dict(pr),
            lines=[],
            blocks=[],
            tables=[],
            warnings=[
                f"page {pr.page_number}: rasterization failed: {pr.error}"
            ],
            silent_empty=False,
        )

    # Single V3 call producing both layout + OCR in one pass (FR-007, R-004).
    # Feature 014 (T021): pass the resolved device.
    lines, blocks, page_tables, run_warnings = ocr.run_page(
        pr.image, pr.page_number, pr.width, pr.height,
        device=_resolve_lane_to_device(invocation.preprocess_lane),
    )
    defensive_warnings, silent_empty = _build_page_warnings(pr, lines, blocks)

    if invocation.write_page_images:
        img_path = invocation.document_folder / f"page_{pr.page_number}.png"
        pr.image.save(img_path)

    # FR-005a / R-011: release the page image before the next page rasterizes.
    try:
        pr.image.close()
    except Exception:
        pass

    return _PageResult(
        page_dict={
            "page_number": pr.page_number,
            "width": pr.width,
            "height": pr.height,
            "rotation_detected": pr.rotation_detected,
            "blocks": blocks,
            "raw_ocr_lines": lines,
        },
        lines=lines,
        blocks=blocks,
        tables=page_tables,
        warnings=run_warnings + defensive_warnings,
        silent_empty=silent_empty,
    )


def _run_inner(invocation: Invocation, stage_timing: StageTiming) -> Path:
    # Feature 014 (T021 / FR-009): on GPU lane, run the inline preflight
    # gate BEFORE any artifact write or input parsing. ensure_gpu_ready
    # is process-cached per Q2.
    if invocation.preprocess_lane != "cpu":
        from ledgerlinc_ocr.preprocessing.preflight import (
            ensure_gpu_ready as _ensure_gpu_ready,
        )
        _ensure_gpu_ready()

    # Feature 016 (T006 / FR-001 / FR-003 / FR-004 / R-016.10): when the
    # warmup opt-in is set AND this is a GPU lane, run exactly one warmup
    # pass after engine adoption (above) and BEFORE the first
    # `measure_phase("rasterization")` opens (below). The lazy import
    # confines GPU-only code to the GPU branch per FR-011 / I-6. The
    # once-per-process guard inside `run_warmup` (`_WARMUP_RAN`) means
    # subsequent calls (e.g., when `_run_inner` is called for doc 2 in a
    # corpus run) are no-ops returning the cached result.
    if invocation.warmup and invocation.preprocess_lane.startswith("gpu"):
        from ledgerlinc_ocr.preprocessing import (
            ocr as _ocr_mod,
            warmup as _warmup_mod,
        )
        # WarmupError propagates to the CLI catch boundary (single-doc
        # `cli.main` and corpus `corpus_run._run_warm_corpus`); both surface
        # exit code 15 + stderr `error: warmup failed: <cause>` per FR-007 /
        # SC-011. No silent fallback (FR-007).
        _warmup_mod.run_warmup(_ocr_mod._ENGINE)

    pdf_path = _validate_input(invocation)
    document_id = _derive_document_id(invocation.document_folder.name)

    pipeline_version = invocation.pipeline_version or build_pipeline_version(
        lane_segment=invocation.preprocess_lane,
    )

    pages: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    warnings_out: list[str] = []
    all_lines: list[dict[str, Any]] = []
    max_skew = 0.0
    pages_with_output = 0
    silent_empty_page_detected = False

    # `measure_phase` records `phases_ns["rasterization"]` even when the
    # iterator raises before yielding (e.g., ZeroPagePdfError on the first
    # `next()`) — the context manager's finally clause guarantees the delta
    # is captured for FR-016 / FP2 partial-failure timings.
    with measure_phase(stage_timing, "rasterization"):
        for pr in rasterize.rasterize_pdf(pdf_path, dpi=DPI):
            result = _process_page(pr, invocation)
            pages.append(result.page_dict)
            warnings_out.extend(result.warnings)
            tables.extend(result.tables)
            all_lines.extend(result.lines)
            if result.lines or result.blocks:
                pages_with_output += 1
            if result.silent_empty:
                silent_empty_page_detected = True

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
