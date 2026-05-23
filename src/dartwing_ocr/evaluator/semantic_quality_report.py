"""Semantic quality gate result types and report-builder (data-model §4-§7).

This module exposes the in-memory result objects the gate returns:

- :class:`FailedCheck` — one entry in the flat ordered
  ``failed_checks`` array (data-model §4 / FR-015 / Q29 / MI-14).
- :class:`RowReasonEntry` — the VALUE inside the
  ``row_reasons`` object; the dict KEY is the ``row_id`` (NOT a field
  on this dataclass). Field names are exactly ``categories`` and
  ``reason`` per the 2026-05-23 F1+F2 remediation (data-model §5 / MI-14).
- :class:`SupportingEvidence` — closed shape on
  ``semantic_table_quality.supporting_evidence`` (data-model §6 / Q37 /
  MI-15). ``body_confidence_min`` is ALWAYS a float, never ``None`` —
  emits ``0.0`` when there are no included body lines (F3 / R-022.12).
- :class:`SemanticQualityResult` — the gate's return value carrying
  ``status`` plus the conditional sub-fields (data-model §7 / FR-016 /
  FR-017).

The corresponding writer (the module that serializes a
:class:`SemanticQualityResult` into ``evaluation_document.json``) lives
under US3 and is NOT part of this US2 phase. US2 returns the in-memory
result only.

Pure stdlib (``dataclasses``, ``decimal``). No Paddle. No network. MI-1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal

from dartwing_ocr.evaluator.semantic_quality_body_ocr import BodyOcrEvidence
from dartwing_ocr.evaluator.stable_json import round_half_even

# Fixed Q17 check-category order — kebab-case literals (MI-12).
CHECK_CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "malformed-currency-shape",
    "missing-required-content",
    "row-text-coverage-gap",
    "row-alignment-failure",
)

# Closed Q26 verdict status set (MI-11).
StatusLiteral = Literal["passed", "failed", "not_applicable", "unevaluable"]

# Closed Q31 unevaluable-cause enum (MI-13).
CauseLiteral = Literal[
    "preprocess_output_missing",
    "preprocess_output_invalid_json",
    "preprocess_output_schema_invalid",
    "body_ocr_unreadable",
]


@dataclass(frozen=True)
class FailedCheck:
    """One entry in the flat ``failed_checks`` array (data-model §4).

    Pinned shape per FR-015 / Q29 / R-022.11. Items are ordered by
    sidecar row declaration order (outer) then by fixed Q17
    check-category order (inner). ``position_index`` is the 0-based
    position in the flat array.
    """

    category: str
    row_id: str
    field: str | None
    expected: str
    observed: str | None
    predicate: str
    position_index: int


@dataclass(frozen=True)
class RowReasonEntry:
    """Per-row aggregation record (data-model §5).

    This is the VALUE inside the ``row_reasons`` object; the dict KEY is
    the ``row_id`` (NOT a field on this dataclass). Field names are
    exactly ``categories`` and ``reason`` (NEVER ``failed_categories`` or
    ``reason_text``) — pinned by F1/F2 / FR-017 / MI-14.

    ``categories`` is a list of kebab-case failed-category labels in the
    fixed Q17 order. ``reason`` is a short one-line human-readable
    summary string.
    """

    categories: list[str]
    reason: str


@dataclass(frozen=True)
class SupportingEvidence:
    """Closed shape on ``semantic_table_quality.supporting_evidence`` (data-model §6).

    Per F3 / R-022.12 / MI-15, ``body_confidence_min`` and
    ``body_confidence_mean`` are ALWAYS float values — never ``None``
    — even when ``body_line_count == 0`` (in which case both emit
    ``0.0``).
    """

    body_confidence_mean: float
    body_confidence_min: float
    body_line_count: int
    body_token_count: int
    header_band_excluded: bool


@dataclass(frozen=True)
class SemanticQualityResult:
    """The gate's in-memory return value (data-model §7 / FR-016 / FR-017).

    The writer that serializes this into ``evaluation_document.json``
    lives under US3 (``evaluator/document.py``) and is NOT part of US2.

    Conditional-field rules (data-model §7):

    - ``failed_checks`` is REQUIRED (always present) when ``status ∈
      {passed, failed, unevaluable}``. Empty list ``[]`` when
      ``passed`` or ``unevaluable``; non-empty when ``failed``.
      ``None`` only when ``status == not_applicable``.
    - ``row_reasons`` is REQUIRED when ``status == failed``; ``None``
      otherwise (NOT an empty dict — the key is absent in the
      serialized output, per MI-14).
    - ``supporting_evidence`` is REQUIRED when ``status ∈ {passed,
      failed, unevaluable}``; MAY be ``None`` when ``status ==
      not_applicable``.
    - ``cause`` is REQUIRED when ``status == unevaluable``; ``None``
      otherwise.
    - ``cause_detail`` is optional even when ``status == unevaluable``.
    """

    status: str
    failed_checks: list[FailedCheck] | None
    supporting_evidence: SupportingEvidence | None
    row_reasons: dict[str, RowReasonEntry] | None = None
    cause: str | None = None
    cause_detail: str | None = None


def _build_supporting_evidence(evidence: BodyOcrEvidence) -> SupportingEvidence:
    """Build the closed-shape :class:`SupportingEvidence` from
    :class:`BodyOcrEvidence`.

    Per Q30 / Q37 / R-022.12 / MI-15:

    - ``body_confidence_mean`` and ``body_confidence_min`` are computed
      ONLY across included body lines.
    - Both are 6-dp ROUND_HALF_EVEN floats.
    - When ``body_line_count == 0`` both emit ``0.0`` (never ``None``).
    """
    lines = evidence.included_lines
    line_count = len(lines)
    token_count = sum(len(line.raw_tokens) for line in lines)
    if line_count == 0:
        mean = 0.0
        minimum = 0.0
    else:
        confidences = [line.detector_confidence for line in lines]
        # Use Decimal for stable 6-dp rounding.
        total = sum(Decimal(repr(c)) for c in confidences)
        mean_decimal = total / Decimal(line_count)
        mean = round_half_even(mean_decimal)
        minimum = round_half_even(Decimal(repr(min(confidences))))
    return SupportingEvidence(
        body_confidence_mean=mean,
        body_confidence_min=minimum,
        body_line_count=line_count,
        body_token_count=token_count,
        header_band_excluded=evidence.header_band_excluded,
    )


def _build_row_reasons(failed_checks: list[FailedCheck]) -> dict[str, RowReasonEntry]:
    """Aggregate ``failed_checks`` into the per-row ``row_reasons`` object.

    Output is keyed by ``row_id``. Each value carries the row's
    distinct failed categories in fixed Q17 order plus a short
    human-readable summary. MI-14: derivable purely from
    ``failed_checks`` — no extra information used.
    """
    per_row: dict[str, list[FailedCheck]] = {}
    for fc in failed_checks:
        per_row.setdefault(fc.row_id, []).append(fc)

    reasons: dict[str, RowReasonEntry] = {}
    for row_id, fcs in per_row.items():
        # Distinct categories preserving fixed Q17 order.
        seen_cats = {fc.category for fc in fcs}
        ordered_cats = [c for c in CHECK_CATEGORY_ORDER if c in seen_cats]
        reasons[row_id] = RowReasonEntry(
            categories=ordered_cats,
            reason=_summarize_row(row_id, fcs),
        )
    return reasons


def _summarize_row(row_id: str, fcs: list[FailedCheck]) -> str:
    """One-line human-readable summary of all failures for a single row.

    Mirrors the form used in the contract Example B (e.g.
    ``"unit_price token '$21:00' fails canonical money regex
    (colon-for-decimal)"``). When multiple categories fire on the same
    row, we join the per-category one-liners with ``"; "``.
    """
    parts: list[str] = []
    for fc in fcs:
        if fc.category == "malformed-currency-shape":
            parts.append(
                f"{fc.field} token '{fc.observed}' fails canonical money regex"
            )
        elif fc.category == "missing-required-content":
            label = fc.field or "required token"
            parts.append(
                f"{label} '{fc.expected}' not found in normalized body-OCR search string"
            )
        elif fc.category == "row-text-coverage-gap":
            parts.append(
                f"required token '{fc.expected}' absent from normalized body-OCR"
            )
        elif fc.category == "row-alignment-failure":
            parts.append(
                f"row content present but cannot be reconstructed within anchored span"
            )
        else:
            # Defensive — should never fire given MI-12.
            parts.append(f"{fc.category}: {fc.expected}")
    return "; ".join(parts)


def build_semantic_quality_result(
    status: str,
    failed_checks: list[FailedCheck],
    evidence: BodyOcrEvidence,
    cause: str | None = None,
    cause_detail: str | None = None,
) -> SemanticQualityResult:
    """Assemble the :class:`SemanticQualityResult` for one document.

    Routes ``status``-driven conditional logic per data-model §7:

    - ``failed_checks`` is always present (empty when no failures);
      ``None`` only when ``status == not_applicable``.
    - ``supporting_evidence`` is always present when ``status ∈
      {passed, failed, unevaluable}``.
    - ``row_reasons`` is built ONLY when ``status == failed``.
    - ``cause`` is recorded ONLY when ``status == unevaluable``.

    The supporting evidence is computed from ``evidence``. Callers MUST
    pass a :class:`BodyOcrEvidence` even on the unevaluable path (it may
    be empty: ``included_lines=()``, ``excluded_line_count=0``, etc.).
    """
    if status == "not_applicable":
        return SemanticQualityResult(
            status=status,
            failed_checks=None,
            supporting_evidence=None,
            row_reasons=None,
            cause=None,
            cause_detail=None,
        )

    supporting = _build_supporting_evidence(evidence)
    row_reasons: dict[str, RowReasonEntry] | None = None
    if status == "failed":
        row_reasons = _build_row_reasons(failed_checks)
    return SemanticQualityResult(
        status=status,
        failed_checks=list(failed_checks),
        supporting_evidence=supporting,
        row_reasons=row_reasons,
        cause=cause if status == "unevaluable" else None,
        cause_detail=cause_detail if status == "unevaluable" else None,
    )
