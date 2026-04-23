"""PaddleOCR `PPStructureV3` wrapper for deterministic CPU inference.

Owns engine construction + per-page inference for the 010 migration (FR-005,
FR-006, FR-007, FR-016 / research R-001, R-002, R-003, R-004, R-005).

V2-era `run_ocr_lines()` and `run_layout()` are deliberately absent — V3's
built-in PP-OCRv5 pass produces both `raw_ocr_lines` and the layout regions
in a single `predict(...)` call (FR-007).
"""

from __future__ import annotations

import re
import warnings as _std_warnings
from typing import Any

import numpy as np
from PIL import Image

from ledgerlinc_ocr.preprocessing.errors import EngineInitError
from ledgerlinc_ocr.preprocessing.identifiers import block_id, line_id
from ledgerlinc_ocr.preprocessing.warnings import build_warning

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


def _get_engine() -> Any:
    """Lazy singleton PPStructureV3 constructor (research R-001). Raises
    `EngineInitError` with structured cause on any init-time exception (FR-016).
    """
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
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
                device="cpu",
                lang="en",
            )
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
    """FR-004 / R-013: persist a single engine-emitted confidence verbatim.

    No clamping to `[0.0, 1.0]`, no normalization. `None` / missing → `None`
    (never `0.0`). Non-numeric values → `None`. The V2-era
    `max(0.0, min(1.0, float(...)))` clamp is deliberately absent.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _persist_confidence(scores: Any, idx: int) -> float | None:
    """FR-004 / R-013: look up `scores[idx]` and persist verbatim.

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
        # FR-004 / R-013: persist confidence verbatim; missing → None, never 0.0.
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
        raw_label = str(_attr(region, "label", "text") or "text").lower()
        if raw_label in PPSTRUCTURE_LABEL_TO_BLOCK_TYPE:
            block_type = PPSTRUCTURE_LABEL_TO_BLOCK_TYPE[raw_label]
        else:
            block_type = "text"
            warnings_out.append(
                build_warning(page_number, "unknown_layout_label", f"label={raw_label}")
            )
        coord = _coalesce(
            _attr(region, "coordinate", None),
            _attr(region, "bbox", None),
            default=[0, 0, 0, 0],
        )
        try:
            bbox = _clip_bbox(_bbox_from_coord(coord), width, height)
        except Exception:
            bbox = [0, 0, 0, 0]
        # FR-004 / R-013: persist layout-region confidence verbatim; missing → None.
        # No default of 0.0 when absent — `None` signals "engine did not emit".
        confidence = _persist_confidence_value(_attr(region, "score", None))

        # Block text content is derived downstream from containing OCR lines
        # (see `_populate_block_text_from_lines`). V3's richer `parsing_res_list`
        # Markdown is discarded at the persistence boundary per research R-002.
        # FR-021 / R-014: raw table HTML is NOT persisted in `block.text`; it is
        # read only to derive `rows`/`columns` via `_parse_table_dims`.
        text = ""
        table_rows = 0
        table_cols = 0
        cells: list[dict[str, Any]] = []

        if block_type == "table" and table_idx < len(table_results):
            tres = table_results[table_idx]
            table_idx += 1
            html = _attr(tres, "html", "") or ""
            if isinstance(html, str) and html:
                table_rows, table_cols = _parse_table_dims(html)
            cell_bboxes = _coalesce(
                _attr(tres, "cell_bbox", None),
                _attr(tres, "cell_boxes", None),
                default=[],
            )
            for ci, cb in enumerate(cell_bboxes):
                row_idx = (ci // table_cols) if table_cols > 0 else 0
                col_idx = (ci % table_cols) if table_cols > 0 else ci
                try:
                    cell_coord = cb[:4] if hasattr(cb, "__len__") and len(cb) >= 4 else cb
                    cell_bbox = _clip_bbox(_bbox_from_coord(cell_coord), width, height)
                except Exception:
                    cell_bbox = [0, 0, 0, 0]
                cells.append(
                    {
                        "row": int(row_idx),
                        "column": int(col_idx),
                        "bbox": cell_bbox,
                        "text": "",
                    }
                )

        staged.append(
            {
                "_det_idx": det_idx,
                "block_type": block_type,
                "bbox": bbox,
                "text": text,
                "confidence": confidence,
                "_table_rows": table_rows,
                "_table_cols": table_cols,
                "_cells": cells,
            }
        )

    staged.sort(key=lambda r: (r["bbox"][1], r["bbox"][0], r["_det_idx"]))

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
    return blocks, tables, warnings_out


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
            if bx0 <= cx <= bx1 and by0 <= cy <= by1:
                if ln["text"]:
                    pieces.append(ln["text"])
        if pieces:
            blk["text"] = " ".join(pieces).strip()


def run_page(
    image: Image.Image,
    page_number: int,
    width: int,
    height: int,
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
    """
    engine = _get_engine()
    warnings_out: list[str] = []
    np_img = np.array(image)
    try:
        with _std_warnings.catch_warnings():
            _std_warnings.simplefilter("ignore")
            results = engine.predict(np_img)
    except Exception as exc:
        warnings_out.append(
            f"page {page_number}: layout extraction failed: {type(exc).__name__}: {exc}"
        )
        return [], [], [], warnings_out

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
