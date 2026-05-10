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
from ledgerlinc_ocr.preprocessing.warmup_optin import is_gpu_lane
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
    # Feature 016 (Copilot PR #24 round 2 finding 1 / FR-007 / SC-004):
    # CLI-intent flag set by the activation surface (`--gpu-warmup` /
    # `LEDGERLINC_GPU_WARMUP=1` AND a GPU lane). Diagnostic only — runtime
    # warmup is driven by `pipeline.run_warmup_if_active()` invoked by the
    # caller BEFORE any `measure_total(stage_timing)` wrapper opens, so
    # warmup duration is excluded from `phase_timings.total.seconds`.
    # `_run_inner` does NOT read this field; tests assert on it to verify
    # the CLI's activation logic produces the expected boolean.
    warmup: bool = False
    # Feature 017 (T009 / T020 / R-017.5 / R-017.8): resolved preset
    # identifier strings threaded from CLI parse → preflight engine
    # construction → run_summary identifier emission. Default `None`
    # means "use the active profile's identity-preset default" (see
    # `preprocessing/identifiers.py::CPU_DEFAULT_*`). On a non-GPU
    # profile, even when the operator set the flag, these stay `None`
    # because the warn-and-proceed branch (FR-013) drops the resolved
    # values — the CPU/stub identifier defaults flow through unchanged.
    module_set_id: str | None = None
    det_rec_variant_id: str | None = None
    # Feature 018 (T009 / T010 / R-018.1 / R-018.2): resolved
    # raster_profile_id string from the CLI parse. Threaded into
    # `_run_inner` so the rasterizer call site uses the resolved DPI
    # (via `raster_profiles.resolve_raster_profile`). Default `None` =
    # use the active profile's identity-preset default DPI (CPU lane
    # always uses the module-level `DPI = 300` per FR-015 / I-018.2).
    # Same warn-and-proceed-nulls-the-value contract as feature 017's
    # two preset axes above.
    raster_profile_id: str | None = None
    # Feature 018 (T019 / T020 / R-018.4 / R-018.7): resolved
    # region_strategy_id string from the CLI parse. Threaded into
    # `_run_inner` so the orchestrator can target a specific page
    # region (via `region_strategies.resolve_region_strategy`). Default
    # `None` = full-page semantics. Same warn-and-proceed-nulls-the-value
    # contract as feature 017's two preset axes above.
    region_strategy_id: str | None = None
    # Feature 018 (T020 / R-018.7 / R-018.8 / Clarifications Q1+Q4):
    # mutable per-document fallback flag. The orchestrator sets this
    # to `True` if the FR-007 trigger fires for this document (and the
    # document is reprocessed under the full-page strategy). The CLI /
    # corpus_run reads this AFTER `pipeline.run()` returns to increment
    # the per-run `RunSummary.region_strategy_fallback_count`
    # accumulator. Always-emit-with-default-False on every run kind.
    region_strategy_fallback_fired: bool = False


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


def run_warmup_if_active(
    *,
    preprocess_lane: str,
    warmup_optin: bool,
    module_set_id: str | None = None,
    det_rec_variant_id: str | None = None,
) -> None:
    """Hoisted GPU warmup helper. Callers MUST invoke this BEFORE wrapping
    ``pipeline.run`` in ``measure_total`` so warmup duration does not
    inflate ``phase_timings.total.seconds`` (FR-007 / SC-004 / Copilot
    PR #24 round-2 finding 1).

    No-op when ``warmup_optin`` is False or the lane is not a GPU lane.
    On the GPU + opt-in branch, calls ``preflight.ensure_gpu_ready()``
    to adopt the engine (process-cached — subsequent calls inside
    ``_run_inner`` are cache hits) and then ``warmup.run_warmup()``
    against the adopted engine. Raises ``WarmupError`` on any failure;
    callers translate that to exit code 15 + the canonical
    ``error: warmup failed: <cause-class>: <message>`` stderr line.

    This helper is the single source of truth for the single-doc GPU
    warmup ordering. The warm-corpus path in ``pipeline/corpus_run.py``
    drives the same ``ensure_gpu_ready(...)`` call but from inside the
    warm factory's ``initialize()`` (so the cached readout is shared
    with the per-document loop) and bracketed by ``WarmProfileRegistry``
    initialization timing rather than this helper's call ordering, so
    it cannot share this helper verbatim — see FR-001 / R-016.10.
    """
    if not warmup_optin:
        return
    if not is_gpu_lane(preprocess_lane):
        return
    from ledgerlinc_ocr.preprocessing.preflight import (
        ensure_gpu_ready as _ensure_gpu_ready,
    )
    from ledgerlinc_ocr.preprocessing import (
        ocr as _ocr_mod,
        warmup as _warmup_mod,
    )
    # Feature 017 (review CRITICAL fix): when this helper is the FIRST
    # ensure_gpu_ready caller in the process (warmup path runs BEFORE
    # `_run_inner` per FR-007 / SC-004), it must thread the resolved
    # presets so the cached readout reflects the operator's choice.
    # Otherwise `_run_inner` would see the cached preset-less readout
    # and the GPU engine would have been constructed with legacy
    # defaults regardless of `--module-set=reduced-v1`.
    _module_set_obj = None
    _det_rec_variant_obj = None
    if module_set_id is not None or det_rec_variant_id is not None:
        from ledgerlinc_ocr.preprocessing.presets import (
            resolve_module_set as _resolve_module_set,
            resolve_det_rec_variant as _resolve_det_rec_variant,
        )
        if module_set_id is not None:
            _module_set_obj = _resolve_module_set(module_set_id)
        if det_rec_variant_id is not None:
            _det_rec_variant_obj = _resolve_det_rec_variant(det_rec_variant_id)
    _ensure_gpu_ready(
        module_set=_module_set_obj,
        det_rec_variant=_det_rec_variant_obj,
    )
    _warmup_mod.run_warmup(_ocr_mod.get_active_engine())


def run(invocation: Invocation, *, stage_timing: Optional[StageTiming] = None) -> Path:
    """Execute the preprocessing pipeline for one document.

    Feature 015 (T016 / R-015.4): when `stage_timing` is provided,
    `run()` records the `rasterization` and `artifact_write` phases via
    `measure_phase`. The caller owns `measure_total` so warm-corpus
    Runner — which already wraps the same StageTiming in
    `measure_total` — does not double-count `total_ns`. When
    `stage_timing` is None, a local one is constructed and `run()`
    wraps the body in `measure_total` itself.

    Feature 016 (Copilot PR #24 round 2 finding 1): warmup MUST be
    invoked by the caller via ``run_warmup_if_active()`` BEFORE
    wrapping this call in ``measure_total``. ``_run_inner`` no longer
    runs warmup (FR-007 / SC-004: warmup time is excluded from
    ``phase_timings.total``).

    Feature 018 (T010 / T018 / R-018.7): when
    ``invocation.region_strategy_id`` resolves to a region-first
    preset (e.g. ``"header-first-v1"``), ``_run_inner`` branches to
    ``_run_region_first_path`` for page 1 + empty records for pages
    2..N (R-018.6 / Clarifications Q2). On the FR-007 fallback trigger
    the orchestrator re-runs the document under the full-page strategy
    on the same engine instance (R-018.9) and MUTATES
    ``invocation.region_strategy_fallback_fired = True`` so the caller
    can accumulate ``RunSummary.region_strategy_fallback_count``. The
    flag is reset to ``False`` at the top of every ``_run_inner`` call.
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


def _scaled_page_pixel_dims(
    width_pt: float,
    height_pt: float,
    *,
    dpi: int,
    snapped_rotation: int,
) -> tuple[int, int]:
    """Return full-render pixel dimensions for a PDF page.

    pypdfium2's full-page render swaps width/height for 90/270 degree
    rotations. Region-first page records must use the same dimensions as
    the full-page path so OCR bboxes and page geometry share one coordinate
    system.
    """
    render_width_pt = float(width_pt)
    render_height_pt = float(height_pt)
    if snapped_rotation in {90, 270}:
        render_width_pt, render_height_pt = render_height_pt, render_width_pt
    return (
        max(rasterize.FALLBACK_WIDTH, int(round(render_width_pt * dpi / 72.0))),
        max(rasterize.FALLBACK_HEIGHT, int(round(render_height_pt * dpi / 72.0))),
    )


def _append_empty_page_records(
    pages: list[dict[str, Any]],
    per_page_geometry: list[tuple[int, int, int, int, bool]],
    *,
    start_index: int,
) -> None:
    for i in range(start_index, len(per_page_geometry)):
        full_w_px, full_h_px, _rot_orig, snapped_rot, _changed_rot = per_page_geometry[i]
        pages.append({
            "page_number": i + 1,
            "width": full_w_px,
            "height": full_h_px,
            "rotation_detected": snapped_rot,
            "blocks": [],
            "raw_ocr_lines": [],
        })


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


def _run_region_first_path(
    *,
    pdf_path: Path,
    region_strategy: Any,
    dpi: int,
    invocation: Invocation,
) -> tuple[
    list[dict[str, Any]],  # pages (page 1 populated + 2..N empty)
    list[str],             # warnings_out
    list[dict[str, Any]],  # tables
    list[dict[str, Any]],  # all_lines
    int,                   # pages_with_output
    bool,                  # silent_empty_page_detected
    bool,                  # trigger_fired
]:
    """Feature 018 (T018 / R-018.5 / R-018.7 / R-018.15 / Clarifications
    Q1+Q2+Q3): execute the header-first-v1 region-strategy path on a
    single PDF.

    Page 1 is rasterized to its targeted band only via
    `rasterize.rasterize_page_band` (R-018.5 / T017); the cropped image
    is fed to `ocr.run_page` and PaddleOCR's crop-relative bboxes are
    translated back to full-page pixel coordinates via
    `region_strategies.translate_bbox` (R-018.15) so
    `preprocess_output.json` field shape stays identical to a full-page
    run (FR-002 / I-018.7).

    Pages 2..N are NOT rasterized and NOT sent to inference; they
    appear in `pages[]` as empty page records with valid geometry
    derived from `pypdfium2.PdfPage.get_size()` (R-018.6) so the
    `pages.length == page_count` invariant is preserved (Clarifications
    Q2 / I-018.6).

    After page 1 processing completes, the FR-007 trigger is evaluated
    via `region_strategy.trigger_fired(blocks)` (Clarifications Q3 /
    R-018.7). On `True`, this function returns `trigger_fired=True` and
    EMPTY collected pages — the caller (`_run_inner`) discards
    everything and re-runs the document under the full-page strategy
    on the same engine instance (R-018.9). On `False`, the function
    returns the collected pages with `trigger_fired=False`.
    """
    pages: list[dict[str, Any]] = []
    warnings_out: list[str] = []
    tables: list[dict[str, Any]] = []
    all_lines: list[dict[str, Any]] = []
    pages_with_output = 0
    silent_empty = False

    # Probe the PDF page count and per-page geometry up front. Use the
    # rasterize module's open_pdf helper so PDF-validity errors (encrypted
    # / malformed / zero-page) propagate identically to the full-page path.
    doc = rasterize.open_pdf(pdf_path)
    try:
        page_count = len(doc)
        # Collect per-page geometry for all pages (cheap; no rasterization).
        # Used to (a) ask region_strategy for page 1's BBox; (b) build empty
        # page records for pages 2..N per R-018.6.
        # H2 fix: floor width/height at FALLBACK_WIDTH/HEIGHT (= 1) so a
        # degenerate tiny PDF page can never produce 0 px and violate the
        # schema's `width >= 1` / `height >= 1` constraint. Mirrors the
        # full-page rasterizer's _metadata_fallback_dims helper
        # (rasterize.py:97).
        # M3 fix: snap rotation once at collection time; rasterize_page_band
        # snaps internally too but its result is not surfaced to us.
        per_page_geometry: list[tuple[int, int, int, int, bool]] = []
        for i in range(page_count):
            page = doc[i]
            try:
                width_pt, height_pt = page.get_size()
                rotation = int(page.get_rotation() or 0)
                snapped_rotation, snapped_changed = rasterize.snap_rotation(rotation)
                full_width_px, full_height_px = _scaled_page_pixel_dims(
                    float(width_pt),
                    float(height_pt),
                    dpi=dpi,
                    snapped_rotation=snapped_rotation,
                )
                per_page_geometry.append((
                    full_width_px,
                    full_height_px,
                    rotation,
                    snapped_rotation,
                    snapped_changed,
                ))
            finally:
                page.close()

        # Page 1: ask the strategy for the targeted region.
        page_1_band = region_strategy.page_targeting(doc, 0)
    finally:
        doc.close()

    if page_1_band is None:
        # Strategy returned None for page 0 — degenerate to full-page on
        # this single page only. The strategy itself is responsible for
        # this branch (e.g., a future preset that opts-out of page 1
        # targeting); for header-first-v1 specifically, page_targeting
        # always returns a BBox for page_index == 0 per R-018.5.
        # Treat as trigger_fired so the caller falls back to full-page.
        return [], [], [], [], 0, False, True

    (
        full_width_px,
        full_height_px,
        rotation_original,
        snapped_rotation,
        snapped_changed,
    ) = per_page_geometry[0]
    # Rasterize ONLY the band of page 1 (R-018.5 / T017). Match the
    # full-page path's page-level failure containment: a crop-render
    # failure yields a schema-valid failed page record instead of aborting
    # the whole document.
    try:
        crop_image, offset_px = rasterize.rasterize_page_band(
            pdf_path=pdf_path,
            page_index=0,
            band_bbox_pt=page_1_band,
            dpi=dpi,
        )
    except Exception as exc:  # noqa: BLE001 - convert page render failure to artifact data
        failure = rasterize.PageRasterFailure(
            page_number=1,
            width=full_width_px,
            height=full_height_px,
            rotation_detected=snapped_rotation,
            error=f"{type(exc).__name__}: {exc}",
        )
        pages.append(_build_failed_page_dict(failure))
        warnings_out.append(
            f"page 1: rasterization failed: {failure.error}"
        )
        _append_empty_page_records(pages, per_page_geometry, start_index=1)
        return (
            pages,
            warnings_out,
            tables,
            all_lines,
            pages_with_output,
            silent_empty,
            False,
        )

    # Build a synthetic PageRaster for `_process_page` to consume. Use
    # the FULL-PAGE width/height (not crop dimensions) so the resulting
    # page record's `width`/`height` reflect the full page per FR-002 /
    # I-018.7 (downstream stages compare against full-page coordinates).
    # H1 fix: surface the actual `rotation_snapped` flag so a rotated
    # page-1 still triggers the rotation-normalized warning per
    # `_build_page_warnings`.
    page_1_raster = rasterize.PageRaster(
        page_number=1,
        width=full_width_px,
        height=full_height_px,
        rotation_detected=snapped_rotation,
        rotation_original=rotation_original,
        rotation_snapped=snapped_changed,
        image=crop_image,
    )
    result = _process_page(page_1_raster, invocation)

    # FR-002 / I-018.7 / R-018.15: translate PaddleOCR's crop-relative
    # bboxes back to full-page pixel coordinates by adding the crop's
    # top-left offset. For header-first-v1 the offset is (0, 0) so the
    # translation is the identity; we still run it unconditionally to
    # honor `region_strategies.translate_bbox`'s documented contract
    # ("orchestrator should ALWAYS run PaddleOCR's bbox returns through
    # this helper") so future presets cropping a non-top-left band do
    # not need to re-add a guard here. The cost is a few additions per
    # bbox — negligible.
    from ledgerlinc_ocr.preprocessing.region_strategies import (
        translate_bbox as _translate_bbox_018,
    )
    dx, dy = offset_px
    for block_dict in result.page_dict.get("blocks", []):
        bbox = block_dict.get("bbox")
        if bbox is not None and len(bbox) == 4:
            block_dict["bbox"] = list(
                _translate_bbox_018(tuple(bbox), (dx, dy))
            )
    for line_dict in result.page_dict.get("raw_ocr_lines", []):
        bbox = line_dict.get("bbox")
        if bbox is not None and len(bbox) == 4:
            line_dict["bbox"] = list(
                _translate_bbox_018(tuple(bbox), (dx, dy))
            )

    # FR-007 trigger evaluation (Clarifications Q3 / R-018.7).
    # Build duck-typed objects with a `text` attribute from the block
    # dicts; `trigger_fired` reads only `text` per I-018.5. The proxy
    # is required: `getattr(some_dict, "text", "")` returns `""` (the
    # default) because Python dicts have no `.text` attribute, so
    # passing the dicts directly would silently make the trigger fire
    # on every document (a real correctness bug).
    class _BlockProxy:
        __slots__ = ("text",)
        def __init__(self, text: str) -> None:
            self.text = text

    _trigger_blocks = [
        _BlockProxy(b.get("text", "")) for b in result.page_dict.get("blocks", [])
    ]
    trigger_fired = region_strategy.trigger_fired(_trigger_blocks)

    if trigger_fired:
        # Caller will discard everything and re-run as full-page (R-018.7).
        return [], [], [], [], 0, False, True

    # Build pages[] with page 1 populated + pages 2..N as empty page
    # records (R-018.6 / Clarifications Q2 / I-018.6).
    pages.append(result.page_dict)
    warnings_out.extend(result.warnings)
    tables.extend(result.tables)
    all_lines.extend(result.lines)
    if result.lines or result.blocks:
        pages_with_output += 1
    if result.silent_empty:
        silent_empty = True

    # R-018.6: empty page records for pages 2..N. `blocks: []` and
    # `raw_ocr_lines: []` are explicitly permitted by the v1.2.0
    # preprocess_output schema. `width` / `height` were computed with the
    # same rotation-aware dimensions as the full-page renderer.
    _append_empty_page_records(pages, per_page_geometry, start_index=1)

    return (
        pages,
        warnings_out,
        tables,
        all_lines,
        pages_with_output,
        silent_empty,
        False,  # trigger_fired = False (clean region-first run)
    )


def _run_inner(invocation: Invocation, stage_timing: StageTiming) -> Path:
    # Feature 018 (H5 fix): defensive reset of the per-document fallback
    # flag at the top of every `_run_inner` call so a re-used Invocation
    # cannot inherit `True` from a prior call. corpus_run constructs a
    # fresh Invocation per document so this is belt-and-braces, but the
    # invariant ("flag reflects THIS run only") is now guaranteed.
    invocation.region_strategy_fallback_fired = False

    # Feature 014 (T021 / FR-009): on GPU lane, run the inline preflight
    # gate BEFORE any artifact write or input parsing. ensure_gpu_ready
    # is process-cached per Q2.
    #
    # Feature 017 (review CRITICAL fix): thread Invocation's resolved
    # preset values into ensure_gpu_ready so the GPU engine constructor
    # receives the use_kwargs splat (R-017.6) and det/rec model-name
    # overrides (R-017.4 Appendix A). Lazy resolution from string ID →
    # preset object happens here so the CLI doesn't need to import the
    # presets module before fail-fast validation.
    if invocation.preprocess_lane != "cpu":
        from ledgerlinc_ocr.preprocessing.preflight import (
            ensure_gpu_ready as _ensure_gpu_ready,
        )
        _module_set_obj = None
        _det_rec_variant_obj = None
        if invocation.module_set_id is not None or invocation.det_rec_variant_id is not None:
            from ledgerlinc_ocr.preprocessing.presets import (
                resolve_module_set as _resolve_module_set,
                resolve_det_rec_variant as _resolve_det_rec_variant,
            )
            if invocation.module_set_id is not None:
                _module_set_obj = _resolve_module_set(invocation.module_set_id)
            if invocation.det_rec_variant_id is not None:
                _det_rec_variant_obj = _resolve_det_rec_variant(invocation.det_rec_variant_id)
        _ensure_gpu_ready(
            module_set=_module_set_obj,
            det_rec_variant=_det_rec_variant_obj,
        )

    # Feature 016 (Copilot PR #24 round 2 finding 1): warmup is no longer
    # invoked here — running it inside `_run_inner` placed it within the
    # caller's `measure_total(stage_timing)` window, inflating
    # `phase_timings.total.seconds` with warmup duration and violating
    # FR-007 / SC-004 ("total excludes warmup"). The hoisted helper
    # `pipeline.run_warmup_if_active(...)` MUST be called by the caller
    # before any timing wrapper opens. `Invocation.warmup` is preserved as
    # a CLI-intent flag for diagnostic purposes but no longer drives
    # runtime behavior here.

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
    #
    # Feature 018 (T010 / R-018.2): resolve the threaded raster_profile_id
    # to the actual integer DPI used for this run. CPU lane / unset flag
    # falls through to the module-level `DPI = 300` per FR-015 / I-018.2.
    # Resolution is CPU-safe (no Paddle import); the closed-vocabulary
    # registry was created in T007.
    _resolved_dpi = DPI
    if invocation.raster_profile_id is not None:
        from ledgerlinc_ocr.preprocessing.raster_profiles import (
            resolve_raster_profile as _resolve_raster_profile_018,
        )
        _resolved_dpi = _resolve_raster_profile_018(invocation.raster_profile_id).dpi

    # Feature 018 (T018 / R-018.4 / R-018.5 / R-018.7): resolve the threaded
    # region_strategy_id and branch on its strategy class. Full-page-class
    # strategies (full-page / cpu-default / stub-default) use the existing
    # rasterize_pdf loop unchanged. The header-first-v1 strategy uses the
    # region-first path: page 1 rasterized via rasterize_page_band, pages
    # 2..N skipped (empty page records per Clarifications Q2 / R-018.6).
    # On FR-007 trigger fire, fall back to full-page on the SAME engine
    # instance per R-018.9 (preserves feature 015 FR-001) and set
    # invocation.region_strategy_fallback_fired so the caller can
    # accumulate region_strategy_fallback_count on RunSummary.
    _resolved_region_strategy = None
    _is_region_first = False
    if invocation.region_strategy_id is not None:
        from ledgerlinc_ocr.preprocessing.region_strategies import (
            resolve_region_strategy as _resolve_region_strategy_018,
        )
        _resolved_region_strategy = _resolve_region_strategy_018(
            invocation.region_strategy_id
        )
        _is_region_first = _resolved_region_strategy.name == "header-first-v1"

    with measure_phase(stage_timing, "rasterization"):
        if _is_region_first and _resolved_region_strategy is not None:
            # Region-first path: page 1 only via rasterize_page_band; pages
            # 2..N as empty page records (R-018.6 / Clarifications Q2).
            (
                _region_pages,
                _region_warnings,
                _region_tables,
                _region_lines,
                _region_pages_with_output,
                _region_silent_empty,
                _trigger_fired,
            ) = _run_region_first_path(
                pdf_path=pdf_path,
                region_strategy=_resolved_region_strategy,
                dpi=_resolved_dpi,
                invocation=invocation,
            )
            if _trigger_fired:
                # FR-007 / R-018.7 / Clarifications Q1: discard the
                # partial region-first output entirely and re-run the
                # document under the full-page strategy on the SAME
                # engine instance. The combined wall-clock cost
                # (region-first attempt + full-page) accumulates into
                # the SAME phase_timings.rasterization key per R-018.10.
                invocation.region_strategy_fallback_fired = True
                for pr in rasterize.rasterize_pdf(pdf_path, dpi=_resolved_dpi):
                    result = _process_page(pr, invocation)
                    pages.append(result.page_dict)
                    warnings_out.extend(result.warnings)
                    tables.extend(result.tables)
                    all_lines.extend(result.lines)
                    if result.lines or result.blocks:
                        pages_with_output += 1
                    if result.silent_empty:
                        silent_empty_page_detected = True
            else:
                pages.extend(_region_pages)
                warnings_out.extend(_region_warnings)
                tables.extend(_region_tables)
                all_lines.extend(_region_lines)
                pages_with_output += _region_pages_with_output
                if _region_silent_empty:
                    silent_empty_page_detected = True
        else:
            # Full-page path (existing code) — unchanged for
            # full-page / cpu-default / stub-default / no-flag runs.
            for pr in rasterize.rasterize_pdf(pdf_path, dpi=_resolved_dpi):
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
