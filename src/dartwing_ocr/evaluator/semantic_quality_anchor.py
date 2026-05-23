"""Row anchoring for the semantic quality gate (data-model §12, FR-012 / Q7 / Q24).

For each sidecar row, ``anchor_rows`` finds the contiguous span of body-OCR
included-line indices that best represents the row's position in the
document body. "Best" is defined by FR-012 / Q7 / Q24 as:

1. **Score by exact-token coverage.** For each candidate span over
   ``BodyOcrEvidence.included_lines``, count the number of the row's
   ``required_row_text_tokens`` whose ``normalize(token)`` appears in the
   span's normalized text. The span with the maximum count wins.
2. **Tie-break by earliest serialization-order position (Q24).** On equal
   counts, prefer the lowest ``(page_index, line_index)`` of the span's
   start line. No geometry, no coordinate tolerance.
3. **Further ties by sidecar declaration order (Q7).** A row earlier in
   the sidecar takes priority when two rows tie on every other metric.

The algorithm enumerates contiguous spans by start/end line index. For an
empty evidence packet the anchor for every row is ``None``. Single-line
spans are valid (start == end).

Pure stdlib + :func:`normalize`. No Paddle. No network. MI-1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    BodyOcrEvidence,
    BodyOcrLine,
)
from dartwing_ocr.evaluator.semantic_quality_normalize import normalize


@dataclass(frozen=True)
class RowAnchor:
    """Anchor span for one row over ``BodyOcrEvidence.included_lines``.

    ``start_line_index`` and ``end_line_index`` are inclusive indices into
    ``BodyOcrEvidence.included_lines``. A single-line anchor has
    ``start == end``.
    """

    row_id: str
    start_line_index: int
    end_line_index: int


def _normalized_span_text(
    included_lines: tuple[BodyOcrLine, ...], start: int, end: int
) -> str:
    """Return the normalized text covering ``included_lines[start..end]``
    (both ends inclusive)."""
    return normalize(" ".join(line.raw_text for line in included_lines[start : end + 1]))


def _count_tokens_present(span_normalized_text: str, required_tokens: list[str]) -> int:
    """Count how many required tokens (after normalization) are present
    as substrings in ``span_normalized_text``."""
    count = 0
    for token in required_tokens:
        nt = normalize(token)
        if not nt:
            continue
        if nt in span_normalized_text:
            count += 1
    return count


def _anchor_one_row(
    evidence: BodyOcrEvidence, required_tokens: list[str]
) -> tuple[int, int] | None:
    """Return ``(start, end)`` for the best span, or ``None`` if no
    included lines exist."""
    lines = evidence.included_lines
    if not lines:
        return None

    # Per data-model §12 / Q24 the tie-break is:
    #   primary  : negative count   (max matched-token count wins)
    #   secondary: start index      (earliest serialization-order start wins)
    # Q24's "further ties broken by sidecar declaration order" rule
    # applies BETWEEN rows, not within a single row's spans. For two
    # equal-count-equal-start spans within one row, the iteration order
    # below — `for end in range(start, n)` reaches smallest `end` first
    # — deterministically resolves the remaining ambiguity via the
    # strict `<` comparator: the first span encountered wins. This
    # matches Q24 without adding the unspecified `end - start` tertiary
    # rule Copilot review flagged on PR #45 (2026-05-23).
    best: tuple[int, int] | None = None  # (-count, start)
    best_span: tuple[int, int] | None = None
    n = len(lines)
    for start in range(n):
        for end in range(start, n):
            span_text = _normalized_span_text(lines, start, end)
            count = _count_tokens_present(span_text, required_tokens)
            key = (-count, start)
            if best is None or key < best:
                best = key
                best_span = (start, end)
    assert best is not None  # n >= 1
    return best_span


def anchor_rows(
    rows: list[Any], evidence: BodyOcrEvidence
) -> dict[str, RowAnchor | None]:
    """Anchor each row in ``rows`` to a span over ``evidence.included_lines``.

    Args:
        rows: Iterable of row objects exposing ``row_id`` and
            ``required_row_text_tokens`` attributes (or matching dict
            keys). The function reads only these two fields, so rows
            constructed by the validator, by a stub class in tests, or by
            a future pydantic model all work equivalently.
        evidence: The :class:`BodyOcrEvidence` for the document.

    Returns:
        A dict keyed by ``row_id`` mapping to a :class:`RowAnchor` or
        ``None`` (when ``evidence.included_lines`` is empty).
    """
    anchors: dict[str, RowAnchor | None] = {}
    for row in rows:
        row_id = _get(row, "row_id")
        tokens = _get(row, "required_row_text_tokens") or []
        if not evidence.included_lines:
            anchors[row_id] = None
            continue
        span = _anchor_one_row(evidence, list(tokens))
        if span is None:
            anchors[row_id] = None
        else:
            start, end = span
            anchors[row_id] = RowAnchor(
                row_id=row_id, start_line_index=start, end_line_index=end
            )
    return anchors


def _get(obj: Any, name: str) -> Any:
    """Read attribute or mapping key ``name`` from ``obj``."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
