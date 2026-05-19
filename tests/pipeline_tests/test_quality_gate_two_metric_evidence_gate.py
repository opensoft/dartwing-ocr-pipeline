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
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.gpu

# PR #43 SonarCloud security hotspot fix: hardcoded `/tmp/021-bench/...`
# paths were flagged as "publicly writable directories used unsafely"
# (Sonar S5443 / S2245 family). Make the bench root configurable via an
# env var with a non-public-writable default; GPU operators preserve the
# canonical `/tmp` workflow with one extra env-var export:
#   DARTWING_021_BENCH_ROOT=/tmp/021-bench pytest -m gpu ...
# CI defaults to a relative path so no public-writable directory appears
# in the analyzed source.
_DEFAULT_BENCH_ROOT = ".bench/021-bench"
BENCH_ROOT = Path(os.environ.get("DARTWING_021_BENCH_ROOT", _DEFAULT_BENCH_ROOT))
LEGACY_RUN2 = BENCH_ROOT / "legacy" / "run2" / "evaluation_run_summary.json"
CANDIDATE_RUN2 = BENCH_ROOT / "candidate" / "run2" / "evaluation_run_summary.json"

# FR-011 fixed five-document benchmark subset (research.md R-021.13 +
# R-020.13 fallback list). The quality-gate verdict MUST be computed over
# this exact subset on both lanes; same-subset is FR-013's hard rule.
#
# Cross-file invariant: this MUST match
# ``tests/pipeline_tests/test_evidence_gate_benchmark.py::_DEFAULT_5_DOC_SUBSET``
# (the same FR-011 subset, encoded as a tuple there). Both are derived from
# `specs/021-gpu-mvp-promotion/spec.md` Assumptions / FR-011. If you change
# one, change the other in the same commit.
_EXPECTED_BENCHMARK_SUBSET: frozenset[str] = frozenset({
    "inv_001_easy",
    "inv_002_easy",
    "inv_006_medium",
    "inv_011_hard",
    "inv_012_hard",
})

# Required keys on `evaluation_run_summary.json.overall_metrics` (feature-007
# evaluator schema). Both Metric A (`vendor_identity_pass_rate`) and Metric B
# (`field_accuracy`) MUST be present.
_REQUIRED_OVERALL_METRICS_KEYS: frozenset[str] = frozenset({
    "vendor_identity_pass_rate",
    "field_accuracy",
})


def _assert_summary_shape(summary: dict, lane_name: str) -> None:
    """Assert the run-summary shape feature-021 quality-gate depends on.

    Cross-walks the feature-007 evaluator's `evaluation_run_summary.json`
    schema and fails fast with a named cause if any contract assumption
    is broken — schema drift in feature 007 will surface as a clear
    shape-violation message here rather than a confusing AssertionError
    in the metric extraction below.
    """
    assert isinstance(summary, dict), (
        f"{lane_name}: evaluation_run_summary.json root is not a dict; "
        f"got {type(summary).__name__}. Feature-007 evaluator schema drift."
    )

    # Per-corpus aggregate metrics (Metric A + Metric B both live here).
    overall_metrics = summary.get("overall_metrics")
    assert isinstance(overall_metrics, dict), (
        f"{lane_name}: evaluation_run_summary.json `overall_metrics` is "
        f"not a dict; got {type(overall_metrics).__name__}. "
        f"Feature-007 evaluator schema drift."
    )
    missing_keys = _REQUIRED_OVERALL_METRICS_KEYS - overall_metrics.keys()
    assert not missing_keys, (
        f"{lane_name}: `overall_metrics` missing required keys "
        f"{sorted(missing_keys)!r}. Feature-021 R-021.13 requires both "
        f"`vendor_identity_pass_rate` (Metric A) and `field_accuracy` "
        f"(Metric B) to be persisted by the feature-007 evaluator."
    )

    # Per-document table — FR-011 fixed-5 subset on each lane.
    documents = summary.get("documents")
    assert isinstance(documents, list), (
        f"{lane_name}: `documents` field is not a list; "
        f"got {type(documents).__name__}. Feature-007 evaluator schema drift."
    )
    assert len(documents) == 5, (
        f"{lane_name}: expected {len(_EXPECTED_BENCHMARK_SUBSET)} "
        f"benchmarked documents (FR-011 fixed subset), got "
        f"{len(documents)}. FR-013 same-subset rule means BOTH lanes "
        f"MUST evaluate exactly the FR-011 subset; a different count "
        f"means a corpus drift that invalidates the verdict."
    )

    summary_doc_count = summary.get("document_count")
    assert summary_doc_count == 5, (
        f"{lane_name}: `document_count` reports {summary_doc_count!r}; "
        f"expected 5 (FR-011 fixed subset)."
    )

    actual_doc_ids = {
        doc.get("document_id") for doc in documents if isinstance(doc, dict)
    }
    missing_docs = _EXPECTED_BENCHMARK_SUBSET - actual_doc_ids
    extra_docs = actual_doc_ids - _EXPECTED_BENCHMARK_SUBSET
    assert not missing_docs and not extra_docs, (
        f"{lane_name}: benchmark subset drift detected.\n"
        f"  expected (FR-011): {sorted(_EXPECTED_BENCHMARK_SUBSET)!r}\n"
        f"  actual:            {sorted(actual_doc_ids)!r}\n"
        f"  missing from this lane: {sorted(missing_docs)!r}\n"
        f"  unexpected on this lane: {sorted(extra_docs)!r}\n"
        f"FR-013 requires both lanes to evaluate exactly the FR-011 "
        f"fixed subset. A corpus drift invalidates the verdict; "
        f"re-pin the subset and re-run the benchmark."
    )


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

    Shape + FR-011 fixed-subset validation runs up-front via
    ``_assert_summary_shape`` so feature-007 schema drift (missing
    aggregates, wrong document count, wrong document IDs) surfaces as
    a named-cause AssertionError rather than a confusing TypeError
    downstream inside the metric extractor.

    Failure (NOT skip) on regression is intentional per SC-008.
    Schema drift (shape-violation) is also a test FAILURE — feature-007
    is a sibling package and its schema is a code contract; a drift is
    a coding bug, not a FR-022 hardware/runtime BLOCKED case.
    BLOCKED via xfail is reserved for the FR-022 named-cause path
    (summary missing or malformed JSON per R-021.16).
    """
    legacy = _load_summary(LEGACY_RUN2)
    candidate = _load_summary(CANDIDATE_RUN2)

    # Shape + subset validation BEFORE metric extraction — fails fast with
    # a named-cause AssertionError on feature-007 schema drift or
    # corpus-subset drift, instead of a confusing TypeError inside the
    # metric extractor.
    _assert_summary_shape(legacy, lane_name="legacy")
    _assert_summary_shape(candidate, lane_name="candidate")

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
