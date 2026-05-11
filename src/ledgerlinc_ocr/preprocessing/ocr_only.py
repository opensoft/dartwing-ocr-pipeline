"""Feature 019: PaddleOCR (det+rec only) wrapper for the OCR-only fast lane.

Sibling of `preprocessing/ocr.py` (PPStructureV3 wrapper, feature 014–018).
Owns engine construction + per-page det+rec inference + deterministic
Y-axis block reassembly + FR-005 combined two-threshold eligibility check
for the `--preprocess-strategy=ocr-only-v1` path.

**Dual-singleton coexistence with `ocr.py`** (I-019.2 / R-019.10):

- `ocr.py:_ENGINE` is PPStructureV3 (existing); this module's
  `_OCR_ENGINE` is `paddleocr.PaddleOCR` (new).
- Each engine is constructed at most once per process **when invoked**.
- An `ocr-only-v1` run with zero fallbacks constructs only `_OCR_ENGINE`;
  `_ENGINE` remains `None` (feature 015 FR-001 explicit exception per
  FR-022).
- An `ocr-only-v1` run with ≥1 fallback constructs both engines (each
  exactly once). Mid-run `_ENGINE` transition from `None` to constructed
  is permitted (R-019.10).
- Both engines bind the same `gpu:0` device when GPU is selected
  (feature 015 FR-006 single-device-per-process guard applies per
  engine).

**CPU-import discipline** (I-019.10): module-load is CPU-safe — no
`paddleocr` import at module level. Paddle imports happen lazily inside
`_get_ocr_engine` on the first GPU predict. Module-level type hints use
``Any`` so a host without Paddle can import this module cleanly (used by
CPU-safe tests; the live GPU path only enters via `_get_ocr_engine`).

**FR-002 / R-019.10 guarantee**: this module invokes PaddleOCR text
detection + text recognition only. It MUST NOT construct PPStructureV3
or call any layout-detection / table-recognition / formula-recognition /
seal-recognition module. The kwargs passed to ``paddleocr.PaddleOCR(...)``
explicitly set ``use_doc_orientation_classify=False``,
``use_doc_unwarping=False``, ``use_textline_orientation=False`` to keep
the predict call as light as possible while still using the same
``text_detection_model_name`` / ``text_recognition_model_name`` variants
as feature 017's ``det_rec_variant_id`` (FR-027 — no new model, no new
download host).

Reference: data-model.md §OcrOnlyLine, §OcrOnlyPagePredict,
§Block-Clustering Output, §OcrOnlyEligibilityRule; research.md R-019.5,
R-019.6, R-019.7, R-019.8, R-019.9, R-019.10; contracts/module-invariants.md
I-019.2, I-019.3, I-019.6, I-019.8, I-019.9, I-019.10.
"""

from __future__ import annotations

import enum
import warnings as _std_warnings
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np
from PIL import Image

from ledgerlinc_ocr.preprocessing.errors import EngineInitError


# ---------------------------------------------------------------------------
# Module-level singleton state (mirrors `ocr.py:_ENGINE` pattern per
# R-019.10 / I-019.2).
# ---------------------------------------------------------------------------

_OCR_ENGINE: Any = None
_OCR_ENGINE_DEVICE: Optional[str] = None


def _get_ocr_engine(
    device: str | None = None,
    *,
    text_detection_model_name: str | None = None,
    text_recognition_model_name: str | None = None,
) -> Any:
    """Return the process-wide ``paddleocr.PaddleOCR`` singleton.

    Mirrors ``ocr.py:_get_engine`` per R-019.10:

    - First call constructs the engine on the requested device (default
      ``"cpu"`` when None) and pins ``_OCR_ENGINE_DEVICE`` to that value.
    - Subsequent calls with the same device (or with ``device=None``)
      return the existing singleton without rebuilding.
    - Subsequent calls with a different non-None device raise
      ``RuntimeError`` — single-device-per-process invariant (feature
      015 FR-006 applied to ``_OCR_ENGINE`` per I-019.2).

    The PaddleOCR construction uses the same det/rec variants exposed by
    feature 017's ``det_rec_variant_id`` (FR-027). Other module toggles
    (orientation classify, unwarping, textline orientation) are forced
    off so the predict call exercises only det+rec per FR-002.
    """
    global _OCR_ENGINE, _OCR_ENGINE_DEVICE
    if _OCR_ENGINE is not None:
        if (
            device is not None
            and _OCR_ENGINE_DEVICE is not None
            and _OCR_ENGINE_DEVICE != device
        ):
            raise RuntimeError(
                f"PaddleOCR engine already constructed for "
                f"device={_OCR_ENGINE_DEVICE!r}; refusing to rebuild for "
                f"device={device!r} (singleton-per-process)"
            )
        return _OCR_ENGINE
    effective_device = device if device is not None else "cpu"
    try:
        # Lazy import — module-load remains CPU-safe (I-019.10).
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]

        with _std_warnings.catch_warnings():
            _std_warnings.simplefilter("ignore")
            _OCR_ENGINE = PaddleOCR(
                text_detection_model_name=text_detection_model_name,
                text_recognition_model_name=text_recognition_model_name,
                # FR-002: explicitly disable the orientation / unwarping
                # / textline-orientation passes — det+rec only.
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                cpu_threads=1,
                enable_mkldnn=False,
                device=effective_device,
                lang="en",
            )
            _OCR_ENGINE_DEVICE = effective_device
    except Exception as exc:
        # Mirror ocr.py's EngineInitError envelope so callers can route
        # OCR-only construction failures the same way as PPStructureV3
        # construction failures.
        raise EngineInitError(
            message=str(exc),
            cause_class=type(exc).__name__,
            cause_module=type(exc).__module__ or "",
        ) from exc
    return _OCR_ENGINE


def get_active_ocr_engine() -> Any:
    """Return the constructed singleton or raise if not yet constructed.

    Used by the warmup pass (Q3 resolution / T035) when the resolved
    `preprocess_strategy_id == "ocr-only-v1"` so warmup binds the OCR-
    only engine instead of PPStructureV3 per I-019.16.
    """
    if _OCR_ENGINE is None:
        raise RuntimeError(
            "ocr_only._OCR_ENGINE is not constructed; "
            "call _get_ocr_engine(device, ...) first."
        )
    return _OCR_ENGINE


# ---------------------------------------------------------------------------
# Value types (data-model.md §OcrOnlyLine, §OcrOnlyPagePredict)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OcrOnlyLine:
    """A single detected and recognized text line from PaddleOCR's pure-
    OCR pass. Internal — not persisted to disk.

    ``bbox`` uses the same coordinate system as the existing
    ``preprocess_output.json`` per-page schema (``[x0, y0, x1, y1]``
    integer pixel space, top-left origin).
    """

    bbox: tuple[int, int, int, int]
    text: str
    detector_confidence: float


@dataclass(frozen=True)
class OcrOnlyPagePredict:
    """Aggregate predict result for one page on the OCR-only path."""

    lines: list[OcrOnlyLine]
    page_number: int
    page_width: int
    page_height: int


# ---------------------------------------------------------------------------
# Per-page predict (FR-002 / R-019.10)
# ---------------------------------------------------------------------------


def run_ocr_only_page(
    engine: Any,
    page_image: Image.Image,
    *,
    page_number: int,
) -> OcrOnlyPagePredict:
    """Run PaddleOCR det+rec on a single page image.

    Returns an `OcrOnlyPagePredict` with the detected lines (bbox + text
    + detector_confidence). The engine must already be constructed via
    `_get_ocr_engine`; the caller is responsible for this so the predict
    path doesn't accidentally rebuild engines mid-run.

    PaddleOCR's `predict()` accepts a NumPy ndarray (HxWx3 uint8) per its
    documented API. We convert the PIL Image to ndarray here so callers
    can pass plain PIL Images (which is what `rasterize.rasterize_pdf`
    and `rasterize.rasterize_page_band` return).
    """
    width, height = page_image.size
    image_array = np.asarray(page_image.convert("RGB"))

    lines: list[OcrOnlyLine] = []
    with _std_warnings.catch_warnings():
        _std_warnings.simplefilter("ignore")
        results = engine.predict(image_array)

    # PaddleOCR.predict() returns a list of result dicts (one per input
    # image). Each result carries `rec_texts`, `rec_scores`, and
    # `rec_polys` (or `dt_polys`) keys. The exact shape varies slightly
    # across paddleocr 3.5.x patches; we read defensively.
    for result in results or []:
        # `result` may be a dict-like or a custom Result object — try
        # attribute access first, fall back to mapping access.
        rec_texts = _result_field(result, "rec_texts") or []
        rec_scores = _result_field(result, "rec_scores") or []
        rec_polys = (
            _result_field(result, "rec_polys")
            or _result_field(result, "dt_polys")
            or []
        )
        for poly, text, score in zip(rec_polys, rec_texts, rec_scores):
            bbox = _polygon_to_bbox(poly, width=width, height=height)
            lines.append(
                OcrOnlyLine(
                    bbox=bbox,
                    text=str(text or ""),
                    detector_confidence=float(score) if score is not None else 0.0,
                )
            )

    return OcrOnlyPagePredict(
        lines=lines,
        page_number=page_number,
        page_width=width,
        page_height=height,
    )


def _result_field(result: Any, name: str) -> Any:
    """Read `name` from a PaddleOCR result object (mapping or attribute)."""
    if hasattr(result, name):
        return getattr(result, name)
    if isinstance(result, dict) and name in result:
        return result[name]
    return None


def _polygon_to_bbox(
    poly: Any, *, width: int, height: int
) -> tuple[int, int, int, int]:
    """Convert an axis-aligned or quad polygon to ``[x0, y0, x1, y1]``
    integer pixel bbox, clamped to page geometry. Same rounding /
    clamping convention as `ocr._bbox_from_coord` + `_clip_bbox`."""
    arr = np.asarray(poly, dtype=float).reshape(-1, 2)
    x0 = int(max(0, np.floor(arr[:, 0].min())))
    y0 = int(max(0, np.floor(arr[:, 1].min())))
    x1 = int(max(0, np.ceil(arr[:, 0].max())))
    y1 = int(max(0, np.ceil(arr[:, 1].max())))
    x0 = min(x0, width)
    y0 = min(y0, height)
    x1 = max(x0, min(x1, width))
    y1 = max(y0, min(y1, height))
    return (x0, y0, x1, y1)


# ---------------------------------------------------------------------------
# Deterministic Y-axis block reassembly (R-019.8 / I-019.8 / I-019.6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OcrOnlyBlock:
    """An OCR-only-derived block. The orchestrator translates this into
    the existing ``preprocess_output.json`` block shape (via
    ``preprocessing/pipeline.py`` block-building helpers); this dataclass
    is the intermediate representation that `cluster_lines_into_blocks`
    returns.
    """

    reading_order: int
    bbox: tuple[int, int, int, int]
    text: str
    block_type: str = "text"  # I-019.6: OCR-only always emits "text"


def cluster_lines_into_blocks(lines: Sequence[OcrOnlyLine]) -> list[OcrOnlyBlock]:
    """Deterministic Y-axis line clustering per R-019.8 / I-019.8.

    Algorithm:

    1. Compute each line's vertical center ``cy = (y_min + y_max) / 2``.
    2. Sort lines by ``cy`` ascending (stable sort).
    3. Compute median line height ``H`` over the input set; the
       proximity threshold is ``1.5 * H`` (no rounding, no clamping).
    4. Greedy clustering: a line joins the current cluster iff its
       ``cy`` is within ``proximity_threshold`` of the previous line's
       ``cy`` (``<=``, inclusive). Otherwise start a new cluster.

    Within each cluster the lines are joined with ``"\\n"`` to form the
    block's ``text`` and the bbox is the per-axis min/max envelope.
    Every block has ``block_type = "text"`` per I-019.6 — OCR-only does
    not run layout classification.

    Empty input ⇒ empty output. Single-line input ⇒ one block.
    """
    if not lines:
        return []
    # 1. Compute (line, cy) tuples
    centers = [
        (line, (line.bbox[1] + line.bbox[3]) / 2.0)
        for line in lines
    ]
    # 2. Sort by cy (stable)
    centers.sort(key=lambda pair: pair[1])
    # 3. Compute median line height (Python lower-median: index = len // 2 of
    #    a sorted list; deterministic across platforms per I-019.8).
    heights = sorted(line.bbox[3] - line.bbox[1] for line in lines)
    median_height = heights[len(heights) // 2]
    proximity_threshold = 1.5 * median_height
    # 4. Greedy clustering
    clusters: list[list[OcrOnlyLine]] = []
    current: list[OcrOnlyLine] = [centers[0][0]]
    last_cy: float = centers[0][1]
    for line, cy in centers[1:]:
        if cy - last_cy <= proximity_threshold:
            current.append(line)
        else:
            clusters.append(current)
            current = [line]
        last_cy = cy
    clusters.append(current)
    # Build OcrOnlyBlock objects
    return [
        _build_block(cluster, reading_order=i + 1)
        for i, cluster in enumerate(clusters)
    ]


def _build_block(cluster: Sequence[OcrOnlyLine], *, reading_order: int) -> OcrOnlyBlock:
    """Construct an OcrOnlyBlock from a cluster of OcrOnlyLines.

    bbox = per-axis min/max envelope. text = lines joined with newline,
    in cluster order (cluster is already sorted by `cy` ascending by the
    caller).
    """
    x0 = min(line.bbox[0] for line in cluster)
    y0 = min(line.bbox[1] for line in cluster)
    x1 = max(line.bbox[2] for line in cluster)
    y1 = max(line.bbox[3] for line in cluster)
    text = "\n".join(line.text for line in cluster)
    return OcrOnlyBlock(
        reading_order=reading_order,
        bbox=(x0, y0, x1, y1),
        text=text,
        block_type="text",
    )


# ---------------------------------------------------------------------------
# FR-005 combined two-threshold eligibility check (R-019.5 / R-019.6 /
# R-019.7 / I-019.3 / I-019.9)
# ---------------------------------------------------------------------------


class EligibilityVerdict(enum.Enum):
    """The two-state output of `check_eligibility`.

    - SUFFICIENT: OCR-only output is accepted as the final
      `preprocess_output.json` for the document.
    - INSUFFICIENT: OCR-only partial output is discarded and the
      document falls back to ``ppstructurev3`` on the same engine
      instance (R-019.10 / I-019.4).
    """

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


def check_eligibility(
    lines: Sequence[OcrOnlyLine],
    *,
    token_threshold: int,
    confidence_threshold: float,
    confidence_aggregator: str = "mean",
) -> EligibilityVerdict:
    """FR-005 combined two-threshold eligibility check.

    Per I-019.3 AND-semantics:

    - Both arms must hold (``token_count >= token_threshold`` AND
      ``mean_confidence >= confidence_threshold``) for SUFFICIENT.
    - If either trips, the document is INSUFFICIENT and falls back.

    Per R-019.7 zero-detection short-circuit:

    - Empty ``lines`` (no boxes detected) ⇒ INSUFFICIENT unconditionally,
      evaluated BEFORE the mean computation (which is undefined on an
      empty input set per I-019.9).

    Per R-019.6, the confidence aggregator is the arithmetic mean of
    per-box detector confidence. Weighted-mean / median / max / min are
    forbidden by I-019.9. The ``confidence_aggregator`` parameter accepts
    only ``"mean"`` at landing; any other value raises ``ValueError``.

    Per R-019.9 tokenization, ``token_count`` is the sum of
    ``len(line.text.split())`` across all lines — Python's default
    `str.split()` honors Unicode whitespace categories.
    """
    if confidence_aggregator != "mean":
        raise ValueError(
            f"unsupported confidence_aggregator: {confidence_aggregator!r}; "
            f"only 'mean' is supported at landing (R-019.6 / I-019.9)"
        )
    # R-019.7: zero-detection short-circuit
    if not lines:
        return EligibilityVerdict.INSUFFICIENT
    # R-019.9: Unicode-whitespace token count
    token_count = sum(len(line.text.split()) for line in lines)
    # R-019.6: arithmetic mean of per-box detector confidence
    mean_confidence = sum(line.detector_confidence for line in lines) / len(lines)
    # I-019.3: AND-semantics
    if token_count >= token_threshold and mean_confidence >= confidence_threshold:
        return EligibilityVerdict.SUFFICIENT
    return EligibilityVerdict.INSUFFICIENT


__all__ = (
    "OcrOnlyLine",
    "OcrOnlyPagePredict",
    "OcrOnlyBlock",
    "EligibilityVerdict",
    "_get_ocr_engine",
    "get_active_ocr_engine",
    "run_ocr_only_page",
    "cluster_lines_into_blocks",
    "check_eligibility",
)
