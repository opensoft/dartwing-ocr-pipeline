"""PaddleOCR + PP-StructureV2 wrapper for deterministic CPU inference (FR-008, FR-009, FR-011a, Decision 2)."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from ledgerlinc_ocr.preprocessing.identifiers import block_id, line_id

PPSTRUCTURE_LABEL_TO_BLOCK_TYPE = {
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
}
ALLOWED_BLOCK_TYPES = {"text", "title", "table", "figure", "header", "footer"}

_OCR_ENGINE = None
_STRUCTURE_ENGINE = None


def _lazy_paddle() -> None:
    import paddle

    try:
        paddle.seed(0)
    except Exception:
        pass


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _lazy_paddle()
        from paddleocr import PaddleOCR

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _OCR_ENGINE = PaddleOCR(
                use_angle_cls=True,
                use_gpu=False,
                lang="en",
                show_log=False,
                cpu_threads=1,
                use_mp=False,
            )
    return _OCR_ENGINE


def _get_structure_engine():
    global _STRUCTURE_ENGINE
    if _STRUCTURE_ENGINE is None:
        _lazy_paddle()
        from paddleocr import PPStructure

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _STRUCTURE_ENGINE = PPStructure(
                table=True,
                ocr=True,
                layout=True,
                use_gpu=False,
                show_log=False,
                cpu_threads=1,
                use_mp=False,
                lang="en",
            )
    return _STRUCTURE_ENGINE


@dataclass
class PageOcrResult:
    blocks: list[dict[str, Any]]
    raw_ocr_lines: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    skew_deg: float
    warnings: list[str]


def _bbox_from_points(points: Any) -> list[int]:
    arr = np.asarray(points, dtype=float).reshape(-1, 2)
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
    """Extract (rows, columns) from a PP-Structure HTML table fragment.

    Returns (0, 0) if the structure can't be parsed. Columns are the max
    cells-per-row; FR-011a allows 0 for unknown.
    """
    if not html:
        return 0, 0
    row_spans = [m.end() for m in _TR_RE.finditer(html)]
    if not row_spans:
        return 0, 0
    row_starts = row_spans
    row_ends = row_starts[1:] + [len(html)]
    max_cols = 0
    for s, e in zip(row_starts, row_ends):
        segment = html[s:e]
        count = len(_TD_TH_RE.findall(segment))
        if count > max_cols:
            max_cols = count
    return len(row_starts), max_cols


def _sort_key_bbox_idx(item: tuple[int, Any]) -> tuple[int, int, int]:
    det_idx, rec = item
    bbox = rec["bbox"]
    return (bbox[1], bbox[0], det_idx)


def run_ocr_lines(
    image: Image.Image, page_number: int, width: int, height: int
) -> tuple[list[dict[str, Any]], list[str]]:
    engine = _get_ocr_engine()
    warnings_out: list[str] = []
    np_img = np.array(image)
    try:
        result = engine.ocr(np_img, cls=True)
    except Exception as exc:
        warnings_out.append(f"page {page_number}: OCR failed: {type(exc).__name__}: {exc}")
        return [], warnings_out
    lines_raw = result[0] if result and len(result) > 0 and result[0] else []
    staged: list[dict[str, Any]] = []
    for det_idx, entry in enumerate(lines_raw or []):
        try:
            box, rec = entry[0], entry[1]
            text = rec[0] if isinstance(rec, (list, tuple)) else ""
            conf = float(rec[1]) if isinstance(rec, (list, tuple)) and len(rec) > 1 else 0.0
            bbox = _clip_bbox(_bbox_from_points(box), width, height)
            staged.append(
                {
                    "_det_idx": det_idx,
                    "bbox": bbox,
                    "text": text if isinstance(text, str) else "",
                    "confidence": max(0.0, min(1.0, conf)),
                }
            )
        except Exception:
            continue
    staged.sort(key=lambda r: (r["bbox"][1], r["bbox"][0], r["_det_idx"]))
    out: list[dict[str, Any]] = []
    for n, r in enumerate(staged, start=1):
        out.append(
            {
                "line_id": line_id(page_number, n),
                "bbox": r["bbox"],
                "text": r["text"],
                "confidence": r["confidence"],
            }
        )
    return out, warnings_out


def run_layout(
    image: Image.Image, page_number: int, width: int, height: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    engine = _get_structure_engine()
    warnings_out: list[str] = []
    np_img = np.array(image)
    try:
        result = engine(np_img)
    except Exception as exc:
        warnings_out.append(
            f"page {page_number}: layout extraction failed: {type(exc).__name__}: {exc}"
        )
        return [], [], warnings_out

    staged: list[dict[str, Any]] = []
    for det_idx, region in enumerate(result or []):
        raw_type = (region.get("type") or "text").lower()
        if raw_type in PPSTRUCTURE_LABEL_TO_BLOCK_TYPE:
            block_type = PPSTRUCTURE_LABEL_TO_BLOCK_TYPE[raw_type]
        else:
            block_type = "text"
            warnings_out.append(
                f"block type '{raw_type}' mapped to 'text' fallback on page {page_number}"
            )
        bbox_raw = region.get("bbox") or [0, 0, 0, 0]
        if len(bbox_raw) == 4:
            bbox = _clip_bbox([int(x) for x in bbox_raw], width, height)
        else:
            bbox = _clip_bbox(_bbox_from_points(bbox_raw), width, height)

        res = region.get("res")
        text_parts: list[str] = []
        confs: list[float] = []
        cells: list[dict[str, Any]] = []
        table_rows = 0
        table_cols = 0

        if isinstance(res, list):
            for r in res:
                if isinstance(r, dict):
                    t = r.get("text")
                    if isinstance(t, str):
                        text_parts.append(t)
                    c = r.get("confidence")
                    if isinstance(c, (int, float)):
                        confs.append(float(c))
        elif isinstance(res, dict):
            html = res.get("html")
            if isinstance(html, str):
                text_parts.append(html)
                table_rows, table_cols = _parse_table_dims(html)
            cell_bbox = res.get("cell_bbox") or []
            for ci, cb in enumerate(cell_bbox):
                row_idx = (ci // table_cols) if table_cols > 0 else 0
                col_idx = (ci % table_cols) if table_cols > 0 else ci
                cells.append(
                    {
                        "row": int(row_idx),
                        "column": int(col_idx),
                        "bbox": _clip_bbox(
                            [int(x) for x in cb[:4]] if len(cb) >= 4 else _bbox_from_points(cb),
                            width,
                            height,
                        ),
                        "text": "",
                    }
                )

        text = " ".join(p for p in text_parts if p).strip()
        confidence = float(sum(confs) / len(confs)) if confs else 0.0
        confidence = max(0.0, min(1.0, confidence))

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
