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


def _count_failed_checks(
    failed_checks,
    failed_check_counts: dict[str, int],
    folder_basename: str,
) -> None:
    """Increment per-category failed-check counts in-place; raise on unknown categories.

    Extracted from :func:`build_metrics_namespace` to reduce cognitive
    complexity per Sonar python:S3776 (was 20, threshold 15). Per
    MI-12 the category set is closed — silent drop would mask upstream
    contract drift, so unknown categories raise ValueError naming the
    offending category, folder, and the closed-set inventory.
    """
    for fc in failed_checks or ():
        if fc.category not in failed_check_counts:
            raise ValueError(
                f"build_metrics_namespace: unknown failed-check "
                f"category {fc.category!r} for folder "
                f"{folder_basename!r} (closed MI-12 set is "
                f"{sorted(failed_check_counts)})"
            )
        failed_check_counts[fc.category] += 1


def _semantic_pass_rate(passed: int, evaluable: int) -> float | None:
    """Compute the semantic_table_quality_pass_rate (passed / evaluable).

    Returns ``None`` when ``evaluable == 0`` (avoid division by zero per
    spec). Otherwise returns a Python ``float`` rounded to 6 dp
    ROUND_HALF_EVEN. Extracted per Sonar python:S3776.
    """
    if evaluable == 0:
        return None
    return round_half_even(Decimal(passed) / Decimal(evaluable))


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
            _count_failed_checks(
                result.failed_checks, failed_check_counts, folder_basename
            )
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
    pass_rate = _semantic_pass_rate(passed, evaluable)

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
