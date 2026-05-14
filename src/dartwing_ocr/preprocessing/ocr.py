"""PaddleOCR `PPStructureV3` wrapper for deterministic CPU inference.

Owns engine construction + per-page inference for the 010 migration (FR-005,
FR-006, FR-007, FR-016 / research R-001, R-002, R-003, R-004, R-005).

V2-era `run_ocr_lines()` and `run_layout()` are deliberately absent — V3's
built-in PP-OCRv5 pass produces both `raw_ocr_lines` and the layout regions
in a single `predict(...)` call (FR-007).
"""

from __future__ import annotations

import math
import re
import warnings as _std_warnings
from typing import Any, Optional

import numpy as np
from PIL import Image

from dartwing_ocr.preprocessing.errors import EngineInitError
from dartwing_ocr.preprocessing.identifiers import block_id, line_id
from dartwing_ocr.preprocessing.warnings import build_warning

# V3 layout labels → frozen v1.0.0 `block_type` enum. Labels not in this map
# fall back to `"text"` and emit the FR-006 `[unknown_layout_label]` warning.
PPSTRUCTURE_LABEL_TO_BLOCK_TYPE: dict[str, str] = {
    # V2-era labels retained for parity across the migration
    "text": "text",
    "title": "title",
    "table": "table",
    "figure": "figure",
    "image": "figure",
    "header": "header",
    "footer": "footer",
    "reference": "text",
    "equation": "text",
    "list": "text",
    # V3-era labels (research R-003)
    "paragraph_title": "title",
    "doc_title": "title",
    "abstract": "text",
    "content": "text",
    "figure_title": "text",
    "formula_number": "text",
    "chart_title": "text",
    "table_title": "text",
    "seal": "text",
}
ALLOWED_BLOCK_TYPES = {"text", "title", "table", "figure", "header", "footer"}

_ENGINE: Any = None
# Feature 014 (T008 / CF4): records the device the singleton _ENGINE was
# bound with on first construction; _get_engine raises RuntimeError on
# any subsequent call requesting a different device (single-device per
# process). None means no engine is constructed yet.
_ENGINE_DEVICE: Optional[str] = None
# Feature 014 (T030) / Feature 015 (R-015.3 / T009): accumulator for
# per-page GPU inference time. Feature 015 reshapes from the legacy
# scalar (total_ns, page_count) to a list of (page_number, ns) tuples
# so callers can emit the new `per_page_inference: [{page, seconds}, …]`
# array required by FR-014. The legacy `take_gpu_inference_seconds()`
# helper is preserved (sums the drained list) for one schema version
# of back-compat. Process-scoped; tests can clear via
# `reset_gpu_inference_ns()`.
_GPU_INFERENCE_NS_BY_PAGE: list[tuple[int, int]] = []


def _record_gpu_inference_ns(page_number: int, ns: int) -> None:
    """Record one page's GPU inference duration (T030 / T010).

    `page_number` is 1-based and matches `preprocess_output.json`'s page
    numbering convention. `ns` is the `time.monotonic_ns()` delta around
    a single `engine.predict(np_img)` call. Negative or zero deltas are
    silently ignored (defensive against clock anomalies)."""
    global _GPU_INFERENCE_NS_BY_PAGE
    if ns > 0:
        _GPU_INFERENCE_NS_BY_PAGE.append((int(page_number), int(ns)))


def take_gpu_inference_per_page() -> Optional[list[tuple[int, float]]]:
    """T009 (R-015.3): drain the accumulator and return per-page records.

    Returns a list of `(page_number, seconds)` tuples (six-decimal-rounded
    seconds), sorted by page number. If a page is inferred more than once
    during one document run (feature 018's region-first fallback reprocesses
    page 1), timings are summed into a single page entry so the emitted
    `per_page_inference` array remains strictly ascending and 1-based.
    Resets the underlying list. Returns `None` if no GPU inference has
    been recorded since the last drain — callers (`corpus_run.py`,
    `preprocessing/cli.py`) treat `None` as "omit the `per_page_inference`
    array per FR-016."
    """
    global _GPU_INFERENCE_NS_BY_PAGE
    if not _GPU_INFERENCE_NS_BY_PAGE:
        return None
    totals_ns_by_page: dict[int, int] = {}
    for page_number, ns in _GPU_INFERENCE_NS_BY_PAGE:
        totals_ns_by_page[int(page_number)] = (
            totals_ns_by_page.get(int(page_number), 0) + ns
        )
    drained = [
        (page_number, round(total_ns / 1e9, 6))
        for page_number, total_ns in sorted(totals_ns_by_page.items())
    ]
    _GPU_INFERENCE_NS_BY_PAGE = []
    return drained


def take_gpu_inference_seconds() -> Optional[float]:
    """Legacy helper preserved for one schema version of back-compat
    (R-015.3). Drains the per-page list and returns the SUM of seconds,
    matching feature 014's `gpu_inference_seconds` flat-key emission.
    Returns None when no inference recorded.
    """
    drained = take_gpu_inference_per_page()
    if drained is None:
        return None
    return round(sum(seconds for _, seconds in drained), 6)


def reset_gpu_inference_ns() -> None:
    """Test-only: clear the accumulator without draining."""
    global _GPU_INFERENCE_NS_BY_PAGE
    _GPU_INFERENCE_NS_BY_PAGE = []
_PADDLE_SEEDED = False


def _present(value: Any) -> bool:
    """Return True when `value` should be treated as populated.

    Paddle/PaddleX frequently surfaces numpy arrays, and evaluating those
    through Python truthiness raises `ValueError: truth value is ambiguous`.
    The V3 wrapper must therefore test "missing" explicitly instead of using
    `or` chains.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    try:
        return len(value) > 0
    except TypeError:
        return True


def _coalesce(*values: Any, default: Any = None) -> Any:
    """Return the first populated value without relying on truthiness."""
    for value in values:
        if _present(value):
            return value
    return default


def get_active_engine() -> Any:
    """Return the adopted PPStructureV3 singleton, or raise ``RuntimeError``
    if no engine has been adopted yet.

    Public accessor for callers that need the engine after preflight /
    warm-corpus initialization has already adopted one (e.g.,
    ``preprocessing.warmup.run_warmup``). Avoids reaching into the
    private ``_ENGINE`` module attribute.
    """
    if _ENGINE is None:
        raise RuntimeError(
            "preprocessing.ocr engine has not been adopted yet. "
            "Run a normal preprocessing entrypoint first — "
            "`preprocessing.preflight.ensure_gpu_ready()` (GPU lane) "
            "or `python -m dartwing_ocr.preprocessing ...` / "
            "`python -m dartwing_ocr.pipeline run ...` — so the "
            "engine is constructed and adopted before requesting it."
        )
    return _ENGINE


def _adopt_engine(engine: Any, device: str) -> None:
    """Persist a PPStructureV3 instance into the runtime singleton.

    Called by `preprocessing.preflight.classify()` to hand off the engine
    constructed during preflight step 6 so the runtime path (`_get_engine`
    on first `run_page` call) reuses it instead of building a second copy
    (R-015.1 / CF5). Sets `_PADDLE_SEEDED = True` because preflight has
    already invoked `paddle.seed(0)` indirectly via PPStructureV3 init.
    Idempotent: calling with an engine when one is already adopted is a
    no-op (the existing CF4 single-device guard catches conflicting
    devices via `_get_engine`).
    """
    global _ENGINE, _ENGINE_DEVICE, _PADDLE_SEEDED
    if _ENGINE is not None:
        return
    _ENGINE = engine
    _ENGINE_DEVICE = device
    _PADDLE_SEEDED = True


def _seed_paddle_once() -> None:
    """FR-005: call `paddle.seed(0)` once before first engine construction."""
    global _PADDLE_SEEDED
    if _PADDLE_SEEDED:
        return
    try:
        import paddle  # type: ignore[import-not-found]

        paddle.seed(0)
    except Exception:
        pass
    _PADDLE_SEEDED = True


_WEIGHT_KEYWORDS_RE = re.compile(r"(model|weight|download|fetch)", re.IGNORECASE)
_WEIGHT_FILE_RE = re.compile(
    r"([A-Za-z0-9_.-]+(?:_infer(?:\.tar)?|\.tar|\.pdparams|\.pdmodel|\.pdiparams))"
)
_URL_RE = re.compile(r"https?://[^\s'\"<>]+")


def _classify_engine_init_exception(exc: Exception) -> tuple[str | None, str | None]:
    """Return (missing_weight, weight_hoster_url) if `exc` looks like a paddle
    weight-download failure, else (None, None). Research R-008.
    """
    module = type(exc).__module__ or ""
    if not (module.startswith("paddlex") or module.startswith("paddleocr")):
        return None, None
    msg = str(exc)
    if not _WEIGHT_KEYWORDS_RE.search(msg):
        return None, None
    file_match = _WEIGHT_FILE_RE.search(msg)
    url_match = _URL_RE.search(msg)
    missing = file_match.group(1) if file_match else "unknown"
    hoster = url_match.group(0) if url_match else "unknown"
    return missing, hoster


def _get_engine(device: Optional[str] = None) -> Any:
    """Lazy singleton PPStructureV3 constructor (research R-001). Raises
    `EngineInitError` with structured cause on any init-time exception (FR-016).

    Feature 014 (T008 / CF4): accepts an optional `device` parameter.
    When the singleton is unconstructed and `device` is None, defaults
    to ``"cpu"`` for backward compatibility with feature-010 callers.
    When `device` is explicitly supplied and the singleton is already
    constructed for a different device, raises ``RuntimeError`` rather
    than silently returning the wrong-device engine — this is the
    single-device-per-process invariant. When `device` is None and the
    singleton already exists, returns the singleton regardless of its
    bound device (callers without device knowledge defer to whatever
    the warm initializer constructed). CPU determinism settings
    (``cpu_threads=1, enable_mkldnn=False``) are preserved on the CPU
    path per FR-017 / SC-006.
    """
    global _ENGINE, _ENGINE_DEVICE
    if _ENGINE is not None:
        if (
            device is not None
            and _ENGINE_DEVICE is not None
            and _ENGINE_DEVICE != device
        ):
            raise RuntimeError(
                f"PPStructureV3 engine already constructed for "
                f"device={_ENGINE_DEVICE!r}; refusing to rebuild for "
                f"device={device!r} (singleton-per-process)"
            )
        return _ENGINE
    effective_device = device if device is not None else "cpu"
    _seed_paddle_once()
    try:
        from paddleocr import PPStructureV3  # type: ignore[import-not-found]

        with _std_warnings.catch_warnings():
            _std_warnings.simplefilter("ignore")
            _ENGINE = PPStructureV3(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_formula_recognition=False,
                use_seal_recognition=False,
                use_chart_recognition=False,
                cpu_threads=1,
                enable_mkldnn=False,
                device=effective_device,
                lang="en",
            )
            _ENGINE_DEVICE = effective_device
    except Exception as exc:
        missing_weight, hoster_url = _classify_engine_init_exception(exc)
        raise EngineInitError(
            message=str(exc),
            cause_class=type(exc).__name__,
            cause_module=type(exc).__module__ or "",
            missing_weight=missing_weight,
            weight_hoster_url=hoster_url,
        ) from exc
    return _ENGINE


def _bbox_from_coord(coord: Any) -> list[int]:
    """Accept axis-aligned 4-tuples or 4-point polygons; return [x0, y0, x1, y1]
    using FR-004's floor/ceil rounding convention.
    """
    arr = np.asarray(coord, dtype=float).reshape(-1, 2)
    x0 = int(max(0, np.floor(arr[:, 0].min())))
    y0 = int(max(0, np.floor(arr[:, 1].min())))
    x1 = int(max(0, np.ceil(arr[:, 0].max())))
    y1 = int(max(0, np.ceil(arr[:, 1].max())))
    return [x0, y0, x1, y1]


def _clip_bbox(bbox: list[int], width: int, height: int) -> list[int]:
    x0, y0, x1, y1 = bbox
    x0 = max(0, min(x0, width))
    y0 = max(0, min(y0, height))
    x1 = max(x0, min(x1, width))
    y1 = max(y0, min(y1, height))
    return [int(x0), int(y0), int(x1), int(y1)]


_TR_RE = re.compile(r"<tr\b[^>]*>", re.IGNORECASE)
_TD_TH_RE = re.compile(r"<t[dh]\b[^>]*>", re.IGNORECASE)


def _parse_table_dims(html: str) -> tuple[int, int]:
    """Extract (rows, columns) from an HTML table fragment. Returns (0, 0)
    when the structure can't be parsed — FR-011a allows 0 for unknown.
    """
    if not html:
        return 0, 0
    row_spans = [m.end() for m in _TR_RE.finditer(html)]
    if not row_spans:
        return 0, 0
    row_ends = row_spans[1:] + [len(html)]
    max_cols = 0
    for s, e in zip(row_spans, row_ends):
        segment = html[s:e]
        count = len(_TD_TH_RE.findall(segment))
        if count > max_cols:
            max_cols = count
    return len(row_spans), max_cols


def _persist_confidence_value(value: Any) -> float | None:
    """Persist one engine confidence value in the schema-permitted domain.

    In-range numeric values are preserved verbatim. Missing, non-numeric,
    non-finite, and out-of-range values are represented as `None` so the
    artifact remains valid under the v1.2 nullable-confidence contract without
    silently clamping engine output.
    """
    if value is None:
        return None
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(conf) or conf < 0.0 or conf > 1.0:
        return None
    return conf


def _persist_confidence(scores: Any, idx: int) -> float | None:
    """FR-004 / R-013: look up `scores[idx]` and persist it if schema-valid.

    Parallel-array length mismatches (e.g., `rec_texts` longer than
    `rec_scores`) produce `None` for the missing-score lines rather than
    dropping them. Non-indexable `scores` also produces `None`.
    """
    try:
        value = scores[idx]
    except (TypeError, KeyError, IndexError):
        return None
    return _persist_confidence_value(value)


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    """Read `obj.name` or `obj[name]`; return default if neither works."""
    if obj is None:
        return default
    if hasattr(obj, name):
        return getattr(obj, name)
    try:
        return obj[name]
    except (TypeError, KeyError, IndexError):
        return default


def _extract_lines(
    overall_ocr_res: Any,
    page_number: int,
    width: int,
    height: int,
) -> list[dict[str, Any]]:
    texts = _coalesce(_attr(overall_ocr_res, "rec_texts", None), default=[])
    boxes = _coalesce(
        _attr(overall_ocr_res, "rec_boxes", None),
        _attr(overall_ocr_res, "rec_polys", None),
        default=[],
    )
    scores = _coalesce(_attr(overall_ocr_res, "rec_scores", None), default=[])
    staged: list[dict[str, Any]] = []
    for det_idx, text in enumerate(texts):
        if det_idx >= len(boxes):
            break
        box = boxes[det_idx]
        # FR-004 / R-013: missing or schema-unusable confidence stays null.
        conf = _persist_confidence(scores, det_idx)
        try:
            bbox = _clip_bbox(_bbox_from_coord(box), width, height)
        except Exception:
            continue
        staged.append(
            {
                "_det_idx": det_idx,
                "bbox": bbox,
                "text": text if isinstance(text, str) else "",
                "confidence": conf,
            }
        )
    staged.sort(key=lambda r: (r["bbox"][1], r["bbox"][0], r["_det_idx"]))
    return [
        {
            "line_id": line_id(page_number, n),
            "bbox": r["bbox"],
            "text": r["text"],
            "confidence": r["confidence"],
        }
        for n, r in enumerate(staged, start=1)
    ]


def _extract_blocks_and_tables(
    layout_det_res: Any,
    table_res_list: Any,
    page_number: int,
    width: int,
    height: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    warnings_out: list[str] = []
    regions = _coalesce(_attr(layout_det_res, "boxes", None), default=[])
    table_results = list(_coalesce(table_res_list, default=[]))
    table_idx = 0

    staged: list[dict[str, Any]] = []
    for det_idx, region in enumerate(regions):
        block_type = _map_region_label(region, page_number, warnings_out)
        table_result = None
        if block_type == "table" and table_idx < len(table_results):
            table_result = table_results[table_idx]
            table_idx += 1
        staged.append(
            _stage_layout_region(
                region=region,
                det_idx=det_idx,
                block_type=block_type,
                table_result=table_result,
                width=width,
                height=height,
            )
        )

    staged.sort(key=lambda r: (r["bbox"][1], r["bbox"][0], r["_det_idx"]))
    blocks, tables = _materialize_blocks_and_tables(staged, page_number)
    return blocks, tables, warnings_out


def _map_region_label(
    region: Any,
    page_number: int,
    warnings_out: list[str],
) -> str:
    raw_label = str(_attr(region, "label", "text") or "text").lower()
    block_type = PPSTRUCTURE_LABEL_TO_BLOCK_TYPE.get(raw_label)
    if block_type is not None:
        return block_type
    warnings_out.append(
        build_warning(page_number, "unknown_layout_label", f"label={raw_label}")
    )
    return "text"


def _safe_bbox(coord: Any, width: int, height: int) -> list[int]:
    try:
        return _clip_bbox(_bbox_from_coord(coord), width, height)
    except Exception:
        return [0, 0, 0, 0]


def _table_projection(
    table_result: Any | None,
    width: int,
    height: int,
) -> tuple[int, int, list[dict[str, Any]]]:
    if table_result is None:
        return 0, 0, []

    html = _attr(table_result, "html", "") or ""
    rows, columns = _parse_table_dims(html) if isinstance(html, str) and html else (0, 0)
    cell_bboxes = _coalesce(
        _attr(table_result, "cell_bbox", None),
        _attr(table_result, "cell_boxes", None),
        default=[],
    )
    cells = [
        _project_table_cell(ci, cb, columns, width, height)
        for ci, cb in enumerate(cell_bboxes)
    ]
    return rows, columns, cells


def _project_table_cell(
    index: int,
    cell_box: Any,
    table_columns: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    row_idx = (index // table_columns) if table_columns > 0 else 0
    col_idx = (index % table_columns) if table_columns > 0 else index
    cell_coord = (
        cell_box[:4]
        if hasattr(cell_box, "__len__") and len(cell_box) >= 4
        else cell_box
    )
    return {
        "row": int(row_idx),
        "column": int(col_idx),
        "bbox": _safe_bbox(cell_coord, width, height),
        "text": "",
    }


def _stage_layout_region(
    *,
    region: Any,
    det_idx: int,
    block_type: str,
    table_result: Any | None,
    width: int,
    height: int,
) -> dict[str, Any]:
    coord = _coalesce(
        _attr(region, "coordinate", None),
        _attr(region, "bbox", None),
        default=[0, 0, 0, 0],
    )
    table_rows, table_cols, cells = _table_projection(table_result, width, height)
    return {
        "_det_idx": det_idx,
        "block_type": block_type,
        "bbox": _safe_bbox(coord, width, height),
        "text": "",
        "confidence": _persist_confidence_value(_attr(region, "score", None)),
        "_table_rows": table_rows,
        "_table_cols": table_cols,
        "_cells": cells,
    }


def _materialize_blocks_and_tables(
    staged: list[dict[str, Any]],
    page_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blocks: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    for n, r in enumerate(staged, start=1):
        bid = block_id(page_number, n)
        blocks.append(
            {
                "block_id": bid,
                "block_type": r["block_type"],
                "bbox": r["bbox"],
                "reading_order": n,
                "text": r["text"],
                "confidence": r["confidence"],
            }
        )
        if r["block_type"] == "table":
            tables.append(
                {
                    "page_number": page_number,
                    "block_id": bid,
                    "bbox": r["bbox"],
                    "rows": r["_table_rows"],
                    "columns": r["_table_cols"],
                    **({"cells": r["_cells"]} if r["_cells"] else {}),
                }
            )
    return blocks, tables


def _populate_block_text_from_lines(
    blocks: list[dict[str, Any]],
    lines: list[dict[str, Any]],
) -> None:
    """Join OCR lines whose centroid falls inside each non-table block's bbox
    into the block's `text` field. Table blocks already carry their HTML.
    """
    for blk in blocks:
        if blk["block_type"] == "table":
            continue
        bx0, by0, bx1, by1 = blk["bbox"]
        pieces: list[str] = []
        for ln in lines:
            lx0, ly0, lx1, ly1 = ln["bbox"]
            cx = (lx0 + lx1) / 2
            cy = (ly0 + ly1) / 2
            if bx0 <= cx <= bx1 and by0 <= cy <= by1 and ln["text"]:
                pieces.append(ln["text"])
        if pieces:
            blk["text"] = " ".join(pieces).strip()


def run_page(
    image: Image.Image,
    page_number: int,
    width: int,
    height: int,
    device: str = "cpu",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    """Run PPStructureV3 on one rasterized page and return `(lines, blocks,
    tables, warnings)` per research R-004.

    - Engine-init failures propagate as `EngineInitError` (FR-016).
    - Runtime failures during per-page inference are caught here and surfaced
      as a free-form `"page N: layout extraction failed: ..."` warning; the
      caller handles FR-003 / FR-018 / FR-019 detection against the returned
      lines / blocks lengths.
    - Feature 014 (T008/T021): the `device` parameter is forwarded to
      `_get_engine(device)` on the first call per process; subsequent
      calls within the same process must use the same device or the
      singleton guard raises `RuntimeError` (CF4 single-device-per-process).
    """
    engine = _get_engine(device=device)
    warnings_out: list[str] = []
    np_img = np.array(image)
    # Feature 014 (T030): capture per-page GPU inference time when the
    # device is a GPU. The value is accumulated into a module-level
    # counter `_GPU_INFERENCE_NS_TOTAL` that callers (corpus_run.py) can
    # read and emit as `gpu_inference_seconds` on the per-document timing
    # entry. CPU runs do not record this counter.
    import time as _time

    _is_gpu_run = isinstance(device, str) and device.startswith("gpu")
    _gpu_start_ns = _time.monotonic_ns() if _is_gpu_run else 0
    try:
        with _std_warnings.catch_warnings():
            _std_warnings.simplefilter("ignore")
            results = engine.predict(np_img)
    except Exception as exc:
        warnings_out.append(
            f"page {page_number}: layout extraction failed: {type(exc).__name__}: {exc}"
        )
        return [], [], [], warnings_out
    finally:
        # T030 / T010 (R-015.3): record per-page GPU inference time
        # (page_number, ns) into the module-level list. CPU runs do not
        # record. Page numbers stay 1-based to match preprocess_output.json.
        if _is_gpu_run:
            _record_gpu_inference_ns(page_number, _time.monotonic_ns() - _gpu_start_ns)

    result: Any = None
    iterable = results if isinstance(results, (list, tuple)) else [results]
    for r in iterable:
        result = r
        break
    if result is None:
        warnings_out.append(
            f"page {page_number}: layout extraction failed: empty V3 result"
        )
        return [], [], [], warnings_out

    overall_ocr_res = _attr(result, "overall_ocr_res", None)
    layout_det_res = _attr(result, "layout_det_res", None)
    table_res_list = _coalesce(_attr(result, "table_res_list", None), default=[])

    lines = (
        _extract_lines(overall_ocr_res, page_number, width, height)
        if overall_ocr_res is not None
        else []
    )
    if layout_det_res is not None:
        blocks, tables, block_warnings = _extract_blocks_and_tables(
            layout_det_res, table_res_list, page_number, width, height,
        )
    else:
        blocks, tables, block_warnings = [], [], []
    warnings_out.extend(block_warnings)
    _populate_block_text_from_lines(blocks, lines)
    return lines, blocks, tables, warnings_out
