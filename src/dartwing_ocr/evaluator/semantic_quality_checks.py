"""Four-predicate evaluation (FR-009 / FR-010 / FR-011 / FR-012 / Q17 / Q18).

Predicates evaluated for every sidecar row in the fixed Q17 order with
**no short-circuit** (MI-3):

    1. ``malformed-currency-shape``  (FR-010 / Q10 / Q16 / Q35)
    2. ``missing-required-content``  (FR-009)
    3. ``row-text-coverage-gap``     (FR-011 — binary)
    4. ``row-alignment-failure``     (FR-012 — anchored-span ordering)

Failed-check category attribution is predicate-based (Q18 / MI-4): a row
MAY record failures in more than one category simultaneously. The
``evaluate_all_rows`` orchestrator emits a flat ordered ``list[FailedCheck]``
with ``position_index`` set deterministically.

Pure stdlib. No Paddle. No network. MI-1.
"""

from __future__ import annotations

from typing import Any

from dartwing_ocr.evaluator.semantic_quality_anchor import (
    RowAnchor,
    anchor_rows,
)
from dartwing_ocr.evaluator.semantic_quality_body_ocr import (
    BodyOcrEvidence,
    BodyOcrLine,
)
from dartwing_ocr.evaluator.semantic_quality_currency import (
    CANONICAL_MONEY_REGEX,
    _digit_sequence,
    locate_currency_token,
)
from dartwing_ocr.evaluator.semantic_quality_normalize import normalize
from dartwing_ocr.evaluator.semantic_quality_report import (
    CHECK_CATEGORY_ORDER,
    FailedCheck,
)

# Currency fields covered by FR-010 (Q9 / Q35).
_CURRENCY_FIELDS: tuple[str, ...] = ("unit_price", "amount")

# Cell-level fields covered by FR-009 missing-required-content.
_CELL_FIELDS: tuple[str, ...] = ("quantity", "description", "unit_price", "amount")


def _get(obj: Any, name: str) -> Any:
    """Read attribute or mapping key ``name`` from ``obj``."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _span_raw_tokens(
    evidence: BodyOcrEvidence, anchor: RowAnchor | None
) -> tuple[tuple[str, ...], list[int]]:
    """Return ``(span_tokens, line_boundary_indices)`` for an anchor.

    The boundary indices list is the cumulative token count per line,
    used to map a token index back to a (page, line) for ordering checks.
    """
    if anchor is None or not evidence.included_lines:
        return ((), [])
    tokens: list[str] = []
    boundaries: list[int] = []
    for i in range(anchor.start_line_index, anchor.end_line_index + 1):
        if i < 0 or i >= len(evidence.included_lines):
            continue
        line = evidence.included_lines[i]
        tokens.extend(line.raw_tokens)
        boundaries.append(len(tokens))
    return (tuple(tokens), boundaries)


# ---------------------------------------------------------------------------
# Predicate: malformed-currency-shape (FR-010 / Q10 / Q16 / Q35)
# ---------------------------------------------------------------------------


def evaluate_currency_shape(
    row: Any,
    anchor: RowAnchor | None,
    evidence: BodyOcrEvidence,
) -> tuple[list[FailedCheck], set[int]]:
    """Evaluate currency-shape for each declared currency field.

    Per Q35 / MI-9: scan tokens in the anchored span in serialization
    order; locate the first not-yet-matched token whose digit sequence
    equals the expected field's digit sequence; evaluate
    :data:`CANONICAL_MONEY_REGEX` against THAT raw token (NOT the
    normalized form — Q16 / MI-8). When no candidate token exists for a
    declared currency field, the failure category is
    ``missing-required-content`` (handled by the missing-content
    predicate), NOT ``malformed-currency-shape``.

    Returns:
        Tuple of (failed checks for this row, indices already matched
        within ``span_tokens``). The indices are returned so the
        downstream missing-content predicate can know not to also flag
        a currency field as missing when the raw token WAS found (just
        malformed).
    """
    row_id = _get(row, "row_id")
    span_tokens, _ = _span_raw_tokens(evidence, anchor)
    failures: list[FailedCheck] = []
    already_matched: set[int] = set()

    for field_name in _CURRENCY_FIELDS:
        expected = _get(row, field_name)
        if expected is None:
            continue
        digit_seq = _digit_sequence(str(expected))
        located = locate_currency_token(span_tokens, digit_seq, already_matched)
        if located is None:
            # No candidate raw token in span → handled by
            # missing-required-content, NOT currency-shape (Q35).
            continue
        idx, raw_token = located
        already_matched.add(idx)
        # Evaluate raw token against canonical money regex (Q10 / Q16).
        if CANONICAL_MONEY_REGEX.fullmatch(raw_token) is None:
            failures.append(
                FailedCheck(
                    category="malformed-currency-shape",
                    row_id=row_id,
                    field=field_name,
                    expected=str(expected),
                    observed=raw_token,
                    predicate=r"raw token must match ^\$?\d{1,3}(,\d{3})*\.\d{2}$",
                    position_index=0,  # set by orchestrator
                )
            )
    return failures, already_matched


# ---------------------------------------------------------------------------
# Predicate: missing-required-content (FR-009)
# ---------------------------------------------------------------------------


def evaluate_missing_required_content(
    row: Any, evidence: BodyOcrEvidence
) -> list[FailedCheck]:
    """Evaluate normalized exact containment for each declared cell field.

    Per FR-009 / Q33 / MI-6: the comparison is against the document's
    single ``evidence.normalized_search_string``. Each declared cell
    value is normalized via :func:`normalize` and checked for substring
    presence.
    """
    row_id = _get(row, "row_id")
    haystack = evidence.normalized_search_string
    failures: list[FailedCheck] = []
    for field_name in _CELL_FIELDS:
        expected = _get(row, field_name)
        if expected is None:
            continue
        needle = normalize(str(expected))
        if not needle:
            continue
        if needle in haystack:
            continue
        failures.append(
            FailedCheck(
                category="missing-required-content",
                row_id=row_id,
                field=field_name,
                expected=str(expected),
                observed=None,
                predicate="normalized exact containment in body-OCR search string",
                position_index=0,
            )
        )
    return failures


# ---------------------------------------------------------------------------
# Predicate: row-text-coverage-gap (FR-011 — binary)
# ---------------------------------------------------------------------------


def evaluate_row_text_coverage(
    row: Any, evidence: BodyOcrEvidence
) -> list[FailedCheck]:
    """Binary FR-011 row-text-coverage check.

    A single missing required token triggers a failure (Q6). All missing
    tokens are recorded as separate :class:`FailedCheck` entries so the
    reviewer can see every gap.
    """
    row_id = _get(row, "row_id")
    haystack = evidence.normalized_search_string
    failures: list[FailedCheck] = []
    tokens = _get(row, "required_row_text_tokens") or []
    for token in tokens:
        nt = normalize(str(token))
        if not nt:
            continue
        if nt in haystack:
            continue
        failures.append(
            FailedCheck(
                category="row-text-coverage-gap",
                row_id=row_id,
                field="required_row_text_tokens",
                expected=str(token),
                observed=f"token '{token}' absent from normalized body-OCR",
                predicate="every required_row_text_token present as normalized substring",
                position_index=0,
            )
        )
    return failures


# ---------------------------------------------------------------------------
# Predicate: row-alignment-failure (FR-012)
# ---------------------------------------------------------------------------


def evaluate_row_alignment(
    row: Any,
    anchor: RowAnchor | None,
    evidence: BodyOcrEvidence,
    currency_match_state: set[int],
) -> list[FailedCheck]:
    """Verify required values appear in order within the anchored span.

    A row records ``row-alignment-failure`` when the required content
    IS present somewhere in the body OCR (so missing-content does NOT
    fire) but is shifted, out of order, or split outside the row's
    anchored span. We approximate this by checking the ordering of the
    located currency-position tokens for the declared (unit_price,
    amount) pair: if ``unit_price``'s span-token index is greater than
    ``amount``'s, the alignment is wrong.

    The check is intentionally narrow at v1 — full row-reconstruction
    semantics are out of scope per FR-012's "first gate" framing.
    """
    if anchor is None:
        return []
    row_id = _get(row, "row_id")
    span_tokens, _ = _span_raw_tokens(evidence, anchor)
    if not span_tokens:
        return []

    located_positions: dict[str, int] = {}
    matched_indices: set[int] = set()
    for field_name in _CURRENCY_FIELDS:
        expected = _get(row, field_name)
        if expected is None:
            continue
        digit_seq = _digit_sequence(str(expected))
        located = locate_currency_token(span_tokens, digit_seq, matched_indices)
        if located is None:
            continue
        idx, _ = located
        matched_indices.add(idx)
        located_positions[field_name] = idx

    # Only emit a row-alignment failure if BOTH unit_price and amount
    # are declared AND their order in the span is inverted.
    if (
        "unit_price" in located_positions
        and "amount" in located_positions
        and located_positions["unit_price"] > located_positions["amount"]
    ):
        return [
            FailedCheck(
                category="row-alignment-failure",
                row_id=row_id,
                field=None,
                expected="unit_price precedes amount in row anchored span",
                observed=(
                    f"unit_price at token index {located_positions['unit_price']} "
                    f"appears after amount at token index {located_positions['amount']}"
                ),
                predicate="anchored span: unit_price token precedes amount token",
                position_index=0,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def evaluate_all_rows(
    rows: list[Any], evidence: BodyOcrEvidence
) -> list[FailedCheck]:
    """Run all four predicates over every row, return the flat ordered array.

    Outer loop: sidecar row declaration order. Inner loop: fixed Q17
    check-category order. No short-circuit (MI-3). ``position_index`` is
    set densely from 0 in the order failures are emitted.
    """
    anchors = anchor_rows(rows, evidence)
    flat: list[FailedCheck] = []

    for row in rows:
        row_id = _get(row, "row_id")
        anchor = anchors.get(row_id)

        # 1. malformed-currency-shape (returns already-matched indices for downstream)
        currency_failures, currency_matched = evaluate_currency_shape(
            row, anchor, evidence
        )
        # 2. missing-required-content
        missing_failures = evaluate_missing_required_content(row, evidence)
        # 3. row-text-coverage-gap
        coverage_failures = evaluate_row_text_coverage(row, evidence)
        # 4. row-alignment-failure
        alignment_failures = evaluate_row_alignment(
            row, anchor, evidence, currency_matched
        )

        # Emit in fixed Q17 order:
        for fc in currency_failures:
            flat.append(_with_position(fc, len(flat)))
        for fc in missing_failures:
            flat.append(_with_position(fc, len(flat)))
        for fc in coverage_failures:
            flat.append(_with_position(fc, len(flat)))
        for fc in alignment_failures:
            flat.append(_with_position(fc, len(flat)))

    return flat


def _with_position(fc: FailedCheck, position: int) -> FailedCheck:
    """Return a copy of ``fc`` with ``position_index`` set."""
    return FailedCheck(
        category=fc.category,
        row_id=fc.row_id,
        field=fc.field,
        expected=fc.expected,
        observed=fc.observed,
        predicate=fc.predicate,
        position_index=position,
    )
