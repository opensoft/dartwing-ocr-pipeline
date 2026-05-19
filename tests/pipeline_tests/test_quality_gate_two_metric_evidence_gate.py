"""Feature 021 / T019 / FR-019 + FR-020: GPU two-metric quality-gate verdict.

Converted from the feature-020 R-020.15 placeholder. Consumes the legacy- and
candidate-lane ``evaluation_run_summary.json`` files produced by the
feature-007 evaluator (run by the operator as T020 against
``/tmp/021-bench/{legacy,candidate}/run2/``) and asserts the FR-020 PASS
conjunction:

- **Metric (a) — aggregate vendor-identity pass rate** (FR-019(a)):
  `overall_metrics.vendor_identity_pass_rate` from each lane's run
  summary. PASS iff `candidate >= legacy`.

- **Metric (b) — corpus field-level accuracy** (FR-019(b)):
  `overall_metrics.field_accuracy` from each lane's run summary. PASS
  iff `candidate >= legacy`.

Both metrics MUST be non-regressing for the verdict to be PASS (FR-020
strict conjunction; one-sided gains do not compensate). If either
regresses → the test FAILS (not skips) so a failing promotion candidate
is visibly rejected per SC-008.

If either lane's `evaluation_run_summary.json` is missing (operator has
not yet produced it via T020, or per-doc `expected.json` was missing
per research.md §R-021.16) the test is BLOCKED, surfaced via
``pytest.xfail(strict=False)`` with the named cause. BLOCKED is NOT a
silent skip — the xfail reason is captured in pytest output and the
operator can find it.

Implementation note on R-021.13 (verification-round revision): the
original research decision named "sum of per-document
`vendor_identity_score`" for metric A and "count of per-document
`vendor_identity_pass` flags" for metric B. Feature-007 emits neither
field at the run-summary level — its `evaluation_run_summary.json`
persists ``documents[i] = {document_id, overall_passed, field_accuracy}``
only (see ``src/dartwing_ocr/evaluator/corpus.py::to_persistable_dict``).
The per-document ``document_pass_fail.vendor_identity_passed`` boolean
exists, but it lives in the per-doc ``evaluation_document.json``, not
in the aggregate run summary.

Additionally, on a fixed-N corpus, ``vendor_identity_pass_rate`` and
"per-document pass count" are monotonically equivalent
(``rate = count / N``), so using both collapses the FR-020 conjunction
into a single check.

To restore an independent two-metric conjunction without changing the
feature-007 schema (FR-032 — no new product behavior in `dartwing_ocr`),
this test reads two persisted aggregates from the run summary:

  Metric A: ``overall_metrics.vendor_identity_pass_rate``
            (boolean-aggregated, vendor-identity-only signal)
  Metric B: ``overall_metrics.field_accuracy``
            (continuous, mean per-document field-level match rate)

These are mathematically independent — a document can clear the
vendor-identity boolean threshold while showing variable field-level
accuracy across the other extracted fields. A regression in metric B
catches subtle quality dips that metric A would not.

Skipped on CPU by the root-conftest ``pytest_collection_modifyitems``
gate (state != ppstructurev3_init_succeeded).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu

LEGACY_RUN2 = Path("/tmp/021-bench/legacy/run2/evaluation_run_summary.json")
CANDIDATE_RUN2 = Path("/tmp/021-bench/candidate/run2/evaluation_run_summary.json")


def _load_summary(path: Path) -> dict:
    """Load and return the parsed JSON; xfail with named cause if missing."""
    if not path.is_file():
        pytest.xfail(
            f"BLOCKED: evaluation_run_summary.json not found at {path}. "
            f"This is a feature-021 R-021.16 named-cause path: either the "
            f"operator has not yet run the feature-007 evaluator (T020) "
            f"over /tmp/021-bench/<lane>/run2/, or one of the benchmark "
            f"documents is missing `expected.json` (which causes the "
            f"evaluator to abort before emitting the run summary). "
            f"Skip-fallback remains opt-in per FR-027 while this verdict "
            f"is BLOCKED."
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        pytest.xfail(
            f"BLOCKED: evaluation_run_summary.json at {path} is unreadable "
            f"or malformed ({type(exc).__name__}: {exc}). Re-run the "
            f"feature-007 evaluator (T020) to regenerate. Skip-fallback "
            f"remains opt-in per FR-027 while this verdict is BLOCKED."
        )


def _extract_metric_a_pass_rate(summary: dict) -> float:
    """FR-019(a) Metric: aggregate vendor-identity pass rate (0.0 - 1.0)."""
    metrics = summary.get("overall_metrics", {})
    rate = metrics.get("vendor_identity_pass_rate")
    if not isinstance(rate, (int, float)):
        raise AssertionError(
            f"evaluation_run_summary.json missing overall_metrics."
            f"vendor_identity_pass_rate or non-numeric; got {rate!r}. "
            f"Feature-007 evaluator schema drift — this is a corpus / "
            f"contract issue, not an FR-019 finding."
        )
    return float(rate)


def _extract_metric_b_field_accuracy(summary: dict) -> float:
    """FR-019(b) Metric: corpus field-level accuracy.

    Reads ``overall_metrics.field_accuracy``, the mean per-document
    field-level match rate across the benchmark corpus. Independent of
    metric A (vendor-identity pass rate) per the module docstring's
    R-021.13 revision rationale.
    """
    metrics = summary.get("overall_metrics", {})
    accuracy = metrics.get("field_accuracy")
    if not isinstance(accuracy, (int, float)):
        raise AssertionError(
            f"evaluation_run_summary.json missing overall_metrics."
            f"field_accuracy or non-numeric; got {accuracy!r}. "
            f"Feature-007 evaluator schema drift — this is a corpus / "
            f"contract issue, not an FR-019 finding."
        )
    return float(accuracy)


def test_quality_gate_two_metric_evidence_gate_gpu() -> None:
    """GPU two-metric verdict: compare legacy and candidate
    ``evaluation_run_summary.json`` files; assert candidate >= legacy on
    BOTH the aggregate vendor-identity pass rate AND the corpus field-
    level accuracy (FR-020 strict conjunction).

    Failure (NOT skip) on regression is intentional per SC-008.
    BLOCKED via xfail when either lane's summary is missing or malformed
    per R-021.16.
    """
    legacy = _load_summary(LEGACY_RUN2)
    candidate = _load_summary(CANDIDATE_RUN2)

    legacy_pass_rate = _extract_metric_a_pass_rate(legacy)
    candidate_pass_rate = _extract_metric_a_pass_rate(candidate)

    legacy_field_accuracy = _extract_metric_b_field_accuracy(legacy)
    candidate_field_accuracy = _extract_metric_b_field_accuracy(candidate)

    # FR-019(a) — aggregate non-regression.
    assert candidate_pass_rate >= legacy_pass_rate, (
        f"FR-020 violation: candidate aggregate vendor-identity pass rate "
        f"{candidate_pass_rate:.4f} < legacy {legacy_pass_rate:.4f} "
        f"(metric A regression). Skip-fallback MUST remain opt-in per "
        f"FR-021 / FR-027."
    )

    # FR-019(b) — corpus field-level accuracy non-regression.
    assert candidate_field_accuracy >= legacy_field_accuracy, (
        f"FR-020 violation: candidate corpus field accuracy "
        f"{candidate_field_accuracy:.4f} < legacy {legacy_field_accuracy:.4f} "
        f"(metric B regression). Skip-fallback MUST remain opt-in per "
        f"FR-021 / FR-027."
    )

    # FR-020 PASS verdict reached. The operator transcribes both metrics into
    # Appendix B (T022). The verdict alone does NOT promote — promotion is
    # an explicit team decision (FR-029, recorded by T028).
