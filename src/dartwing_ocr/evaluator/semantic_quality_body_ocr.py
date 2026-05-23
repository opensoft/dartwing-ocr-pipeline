"""Body OCR evidence extraction for the semantic quality gate (data-model §3).

Builds a :class:`BodyOcrEvidence` from a parsed ``preprocess_output.json``
object — every ``raw_ocr_lines[*]`` entry on every page, in serialization
order (Q24), EXCEPT the page-1 header-band region defined by
``EVIDENCE_GATE_Y_THRESHOLD_FRACTION = 0.25``.

Per MI-7 / R-022.4, the y-threshold constant is imported from
:mod:`dartwing_ocr.preprocessing.evidence_gate` (feature 020) and
re-exported here as ``EVIDENCE_GATE_Y_THRESHOLD_FRACTION``. The exclusion
filter applies ONLY to page 1; pages 2..N are fully included.

The single ``normalized_search_string`` is built once per document (Q33 /
MI-6): all included lines joined with a single ASCII space, then the
FR-009 normalization pipeline applied once. All "found anywhere" checks
operate against this string.

Lane-robust: the build does not consult ``blocks`` or ``tables`` (Q22 /
FR-007). It operates only on ``pages[*].raw_ocr_lines[*]`` so it produces
the same result on OCR-only-lane and PPStructureV3 outputs.

Pure stdlib (``dataclasses``, ``math``). No Paddle. No network. MI-1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Final, Mapping

from dartwing_ocr.evaluator.semantic_quality_normalize import normalize
from dartwing_ocr.preprocessing.evidence_gate import (
    Y_THRESHOLD_FRACTION as _EG_Y_THRESHOLD_FRACTION,
)

# Re-export under an explicit name so callers (and reviewers) can see
# that the value comes from preprocessing.evidence_gate (MI-7 / R-022.4).
EVIDENCE_GATE_Y_THRESHOLD_FRACTION: Final[float] = _EG_Y_THRESHOLD_FRACTION


@dataclass(frozen=True)
class BodyOcrLine:
    """One body-OCR line surviving the header-band exclusion filter."""

    raw_text: str
    detector_confidence: float
    page_index: int
    line_index: int
    raw_tokens: tuple[str, ...]


@dataclass(frozen=True)
class BodyOcrEvidence:
    """All body-OCR evidence used by the semantic quality gate.

    ``included_lines`` is in ``preprocess_output.json`` serialization
    order (Q24). ``normalized_search_string`` is the single search target
    for FR-009 / FR-011 / FR-012 "found anywhere" checks (Q33 / MI-6).
    """

    included_lines: tuple[BodyOcrLine, ...]
    excluded_line_count: int
    normalized_search_string: str
    header_band_excluded: bool


def _coerce_float(value: Any) -> float | None:
    """Coerce ``value`` to a positive finite float, or ``None`` on failure.

    Mirrors the fail-closed pattern in
    :func:`dartwing_ocr.preprocessing.evidence_gate._bbox_top_y`:
    booleans are rejected (``float(True) == 1.0`` would silently coerce).
    """
    if isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _line_top_y(line: Mapping[str, Any]) -> float | None:
    """Return the top-y coordinate of a raw OCR line's bbox.

    Schema convention: ``bbox == [x1, y1, x2, y2]`` with ``y1 <= y2``.
    Fails closed on malformed bbox (length != 4, non-numeric coords,
    bool coord, inverted y2 < y1).
    """
    bbox = line.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    if any(isinstance(c, bool) for c in bbox):
        return None
    y1 = _coerce_float(bbox[1])
    y2 = _coerce_float(bbox[3])
    if y1 is None or y2 is None:
        return None
    if y2 < y1:
        return None
    return y1


def build_body_ocr_evidence(preprocess_output_dict: Mapping[str, Any]) -> BodyOcrEvidence:
    """Build the body-OCR evidence packet for one document.

    Args:
        preprocess_output_dict: A parsed ``preprocess_output.json`` content
            object (already JSON-decoded). The function does NOT validate
            it against the schema — schema validation is the gate's
            responsibility (see :mod:`semantic_quality`).

    Returns:
        A :class:`BodyOcrEvidence` carrying every body line surviving the
        header-band filter, in serialization order, plus the document's
        single normalized search string.
    """
    included: list[BodyOcrLine] = []
    excluded_count = 0
    header_band_excluded = False

    pages = preprocess_output_dict.get("pages") if isinstance(preprocess_output_dict, Mapping) else None
    if not isinstance(pages, (list, tuple)):
        pages = []

    for page_index, page in enumerate(pages):
        if not isinstance(page, Mapping):
            continue
        raw_lines = page.get("raw_ocr_lines")
        if not isinstance(raw_lines, (list, tuple)):
            continue

        # Page-1 header-band filter only.
        threshold_y: float | None = None
        if page_index == 0:
            height = _coerce_float(page.get("height"))
            if height is not None and height > 0:
                threshold_y = height * EVIDENCE_GATE_Y_THRESHOLD_FRACTION

        for line_index, line in enumerate(raw_lines):
            if not isinstance(line, Mapping):
                continue
            text = line.get("text")
            if not isinstance(text, str):
                continue

            # Page-1 header-band exclusion.
            if page_index == 0 and threshold_y is not None:
                top_y = _line_top_y(line)
                if top_y is None:
                    # Fail-closed: drop malformed-bbox lines on page 1
                    # (we cannot decide whether they belong to body).
                    excluded_count += 1
                    header_band_excluded = True
                    continue
                if top_y < threshold_y:
                    excluded_count += 1
                    header_band_excluded = True
                    continue
            elif page_index == 0 and threshold_y is None:
                # Cannot compute the threshold on page 1 (missing/zero/
                # non-finite height). Fail closed.
                excluded_count += 1
                header_band_excluded = True
                continue

            confidence = line.get("confidence")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
                # Treat missing/non-numeric confidence as 0.0 — it still
                # contributes a line, but with zero confidence weight.
                detector_conf = 0.0
            else:
                detector_conf = float(confidence)

            included.append(
                BodyOcrLine(
                    raw_text=text,
                    detector_confidence=detector_conf,
                    page_index=page_index,
                    line_index=line_index,
                    raw_tokens=tuple(text.split()),
                )
            )

    # Build the single normalized search string by joining all included
    # raw_text values with a single ASCII space, then applying normalize()
    # once (Q33 / MI-6).
    joined = " ".join(line.raw_text for line in included)
    normalized = normalize(joined)

    return BodyOcrEvidence(
        included_lines=tuple(included),
        excluded_line_count=excluded_count,
        normalized_search_string=normalized,
        header_band_excluded=header_band_excluded,
    )
