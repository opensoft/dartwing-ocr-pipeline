"""Human-readable Markdown run report (§FR-021, research.md §14)."""

from __future__ import annotations

from typing import Sequence

from ledgerlinc_ocr.evaluator.corpus import RunSummary
from ledgerlinc_ocr.evaluator.document import DocumentEvaluation
from ledgerlinc_ocr.evaluator.scoring import (
    FIELD_WEIGHTS,
    SCORED_FIELDS,
    ResultLabel,
)


_DIFFICULTY_ORDER: tuple[str, ...] = ("easy", "medium", "hard", "missing_name")

_FAILING_LABELS: dict[ResultLabel, str] = {
    ResultLabel.MISMATCH: "mismatch",
    ResultLabel.MISSING_PREDICTION: "missing",
    ResultLabel.UNEXPECTED_PREDICTION: "unexpected",
}

_SCORED_FIELDS_INDEX: dict[str, int] = {name: i for i, name in enumerate(SCORED_FIELDS)}


def summarize_failure(doc_evaluation: DocumentEvaluation) -> str:
    """One-line reason for a failing document.

    Derived from `document_pass_fail` plus the top failing `field_results`
    sorted by `FIELD_WEIGHTS` descending, ties broken by `SCORED_FIELDS`
    order; include at most 2 failing fields per document.
    """
    ranked: list[tuple[int, int, str, ResultLabel]] = []
    for fr in doc_evaluation.field_results:
        if fr.result in _FAILING_LABELS:
            weight = FIELD_WEIGHTS[fr.field_name]
            idx = _SCORED_FIELDS_INDEX[fr.field_name]
            ranked.append((-weight, idx, fr.field_name, fr.result))
    ranked.sort()
    top = ranked[:2]
    if top:
        return "; ".join(f"{name} {_FAILING_LABELS[label]}" for _, _, name, label in top)
    return f"document_score {doc_evaluation.document_score:.3f} below threshold"


def render_run_summary(
    run_summary: RunSummary,
    document_evaluations: Sequence[DocumentEvaluation] = (),
) -> str:
    """Render the canonical Markdown run summary per research.md §14.

    The returned string always ends with a single trailing newline.
    Ordering is deterministic: difficulty rows in fixed order, failing
    documents sorted ascending by `document_id`.
    """
    s = run_summary
    by_id = {ev.document_id: ev for ev in document_evaluations}
    lines: list[str] = []

    lines.append("# Stage 1 Evaluation Run Summary")
    lines.append("")
    lines.append(f"- Run ID: {s.run_id}")
    lines.append(f"- Document count: {s.document_count}")
    lines.append(
        f"- Overall pass rate: {s.overall_metrics.overall_document_pass_rate:.3f}"
    )
    lines.append(
        f"- Vendor identity pass rate: {s.overall_metrics.vendor_identity_pass_rate:.3f}"
    )
    lines.append(
        f"- Review routing pass rate: {s.overall_metrics.review_routing_pass_rate:.3f}"
    )
    lines.append(f"- Field accuracy: {s.overall_metrics.field_accuracy:.3f}")
    lines.append("")

    lines.append("## By difficulty")
    lines.append("")
    lines.append("| Difficulty | Docs | Field accuracy | Pass rate |")
    lines.append("|---|---|---|---|")
    for key in _DIFFICULTY_ORDER:
        stats = s.by_difficulty[key]
        lines.append(
            f"| {key} | {stats.document_count} | "
            f"{stats.field_accuracy:.3f} | {stats.overall_document_pass_rate:.3f} |"
        )
    lines.append("")

    lines.append("## Failing documents")
    lines.append("")
    failing = sorted(
        (d for d in s.documents if not d.overall_passed),
        key=lambda d: d.document_id,
    )
    if not failing:
        lines.append("_All documents passed._")
    else:
        for d in failing:
            ev = by_id.get(d.document_id)
            if ev is not None:
                difficulty = ev.difficulty
                reason = summarize_failure(ev)
            else:
                difficulty = "?"
                reason = "evaluation detail unavailable"
            lines.append(f"- {d.document_id} ({difficulty}) — {reason}")
    lines.append("")

    return "\n".join(lines)
