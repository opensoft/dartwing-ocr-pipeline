"""Feature 022 — corpus-level aggregation of semantic gate verdicts (data-model §8).

Public surface:

- :func:`build_metrics_namespace` — compute the eight
  ``semantic_table_quality_metrics`` fields from a list of per-document
  ``SemanticQualityResult`` objects (FR-018 / Q19 / Q36 / Q39).

Calibration folders (those whose basename does NOT match
:data:`corpus_pattern.CANONICAL_FOLDER_PATTERN`) are EXCLUDED from all
aggregate counts per Q39 / MI-20. They still appear in the per-document
``semantic_document_statuses`` array (emitted by the run-summary writer);
the exclusion logic lives here and is the single source of truth for the
``semantic_table_quality_metrics`` namespace.

Pure stdlib (``decimal`` for ROUND_HALF_EVEN pass-rate rounding). No
Paddle, no network. MI-1.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Iterable

from dartwing_ocr.evaluator.semantic_quality_report import (
    SemanticQualityResult,
)
from dartwing_ocr.evaluator.stable_json import round_half_even
from dartwing_ocr.validator.corpus_pattern import is_scored_corpus_folder

# Fixed Q17 check-category order — kebab-case literals (MI-12). Mirrors
# semantic_quality_report.CHECK_CATEGORY_ORDER but duplicated here so this
# module does not depend on a sibling module's private detail.
_FAILED_CHECK_CATEGORIES: Final[tuple[str, ...]] = (
    "malformed-currency-shape",
    "missing-required-content",
    "row-text-coverage-gap",
    "row-alignment-failure",
)


def build_metrics_namespace(
    per_document_results: Iterable[tuple[str, SemanticQualityResult]],
) -> dict:
    """Aggregate per-document gate verdicts into the run-summary metrics namespace.

    Args:
        per_document_results: Iterable of ``(folder_basename,
            SemanticQualityResult)`` tuples — one entry per document
            processed in the run. The ``folder_basename`` (NOT the
            absolute path) is what's matched against
            ``CANONICAL_FOLDER_PATTERN`` to decide scored vs calibration.

    Returns:
        Eight-field dict matching the ``semantic_table_quality_metrics``
        schema in ``contracts/stage1_vendor_identity/v1.3.0/
        evaluation_run_summary.schema.json``. The
        ``semantic_table_quality_pass_rate`` field is a Python ``float``
        rounded to 6 dp ROUND_HALF_EVEN, or ``None`` when
        ``semantic_evaluable_document_count == 0``. The
        ``semantic_failed_check_counts`` sub-object always carries all
        four kebab-case keys (defaulting to 0 — never sparse).

    Calibration folders (those whose basename does not match
    :data:`corpus_pattern.CANONICAL_FOLDER_PATTERN`) are EXCLUDED from
    all aggregate counts AND from the per-category failed-check counts
    per Q39 / MI-20 / SC-009. They still appear in
    ``semantic_document_statuses`` (emitted by the run-summary writer, not
    by this function).
    """
    applicable = 0
    not_applicable = 0
    passed = 0
    failed = 0
    unevaluable = 0
    failed_check_counts: dict[str, int] = dict.fromkeys(_FAILED_CHECK_CATEGORIES, 0)

    for folder_basename, result in per_document_results:
        if not is_scored_corpus_folder(folder_basename):
            # Calibration folder — excluded from aggregates (Q39 / MI-20).
            continue
        status = result.status
        if status == "not_applicable":
            not_applicable += 1
            continue
        # Sidecar was present → applicable to the semantic gate.
        applicable += 1
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
            # Sum per-category failed-check counts from this document.
            for fc in result.failed_checks or ():
                if fc.category in failed_check_counts:
                    failed_check_counts[fc.category] += 1
        elif status == "unevaluable":
            unevaluable += 1
        else:
            # MI-11 — invalid status string. Aggregator MUST raise rather
            # than silently coerce. Reaching this branch is a programmer
            # error (the gate's MI-11 guard should have caught it first).
            raise ValueError(
                f"build_metrics_namespace: invalid status {status!r} for "
                f"folder {folder_basename!r}"
            )

    evaluable = passed + failed

    # Pass rate: passed / evaluable, 6-dp ROUND_HALF_EVEN. null when evaluable == 0.
    if evaluable == 0:
        pass_rate: float | None = None
    else:
        pass_rate = round_half_even(Decimal(passed) / Decimal(evaluable))

    return {
        "semantic_applicable_document_count": applicable,
        "semantic_not_applicable_document_count": not_applicable,
        "semantic_evaluable_document_count": evaluable,
        "semantic_passed_document_count": passed,
        "semantic_failed_document_count": failed,
        "semantic_unevaluable_document_count": unevaluable,
        "semantic_table_quality_pass_rate": pass_rate,
        "semantic_failed_check_counts": failed_check_counts,
    }
