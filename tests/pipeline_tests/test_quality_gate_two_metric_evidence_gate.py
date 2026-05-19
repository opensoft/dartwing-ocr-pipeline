"""Feature 021 / T019 / FR-019 + FR-020: GPU two-metric quality-gate verdict.

Converted from the feature-020 R-020.15 placeholder. Consumes the legacy- and
candidate-lane ``evaluation_run_summary.json`` files produced by the
feature-007 evaluator (run by the operator as T020 against
``/tmp/021-bench/{legacy,candidate}/run2/``) and asserts the FR-020 PASS
conjunction:

- **Metric (a) — aggregate vendor-identity pass rate** (FR-019(a),
  research.md §R-021.13 in spirit): `overall_metrics.vendor_identity_pass_rate`
  from each lane's run summary. PASS iff `candidate >= legacy`.

- **Metric (b) — per-document pass count** (FR-019(b)): the count of
  `documents[i].document_pass_fail.vendor_identity_passed == True` in
  each lane's run summary. PASS iff `candidate >= legacy`.

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

Implementation note on R-021.13: the research decision describes the
aggregate as "sum of per-document vendor_identity_score". feature-007
does NOT emit a per-document `vendor_identity_score` numeric (the
schema has `document_pass_fail.vendor_identity_passed` boolean only),
so this test uses the equivalent `overall_metrics.vendor_identity_pass_rate`
which IS emitted. The two are mathematically equivalent for a fixed-
size subset (`pass_rate = pass_count / count`), and the schema-emitted
field is the auditable choice.

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


def _extract_metric_b_pass_count(summary: dict) -> int:
    """FR-019(b) Metric: per-document pass count.

    Sums the per-document `document_pass_fail.vendor_identity_passed`
    booleans across the corpus.
    """
    documents = summary.get("documents", [])
    if not isinstance(documents, list):
        raise AssertionError(
            f"evaluation_run_summary.json `documents` field is not a list; "
            f"got {type(documents).__name__}. Feature-007 evaluator schema drift."
        )
    count = 0
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        pass_fail = doc.get("document_pass_fail") or {}
        if pass_fail.get("vendor_identity_passed") is True:
            count += 1
    return count


def test_quality_gate_two_metric_evidence_gate_gpu(tmp_path: Path) -> None:
    """GPU two-metric verdict: compare legacy and candidate
    ``evaluation_run_summary.json`` files; assert candidate >= legacy on
    BOTH the per-corpus aggregate vendor-identity pass rate AND the
    per-document pass count (FR-020 strict conjunction).

    Failure (NOT skip) on regression is intentional per SC-008.
    BLOCKED via xfail when either lane's summary is missing or malformed
    per R-021.16.
    """
    legacy = _load_summary(LEGACY_RUN2)
    candidate = _load_summary(CANDIDATE_RUN2)

    legacy_pass_rate = _extract_metric_a_pass_rate(legacy)
    candidate_pass_rate = _extract_metric_a_pass_rate(candidate)

    legacy_pass_count = _extract_metric_b_pass_count(legacy)
    candidate_pass_count = _extract_metric_b_pass_count(candidate)

    # FR-019(a) — aggregate non-regression.
    assert candidate_pass_rate >= legacy_pass_rate, (
        f"FR-020 violation: candidate aggregate vendor-identity pass rate "
        f"{candidate_pass_rate:.4f} < legacy {legacy_pass_rate:.4f} "
        f"(metric A regression). Skip-fallback MUST remain opt-in per "
        f"FR-021 / FR-027."
    )

    # FR-019(b) — per-document pass count non-regression.
    assert candidate_pass_count >= legacy_pass_count, (
        f"FR-020 violation: candidate per-document pass count "
        f"{candidate_pass_count} < legacy {legacy_pass_count} "
        f"(metric B regression). Skip-fallback MUST remain opt-in per "
        f"FR-021 / FR-027."
    )

    # FR-020 PASS verdict reached. The operator transcribes both metrics into
    # Appendix B (T022). The verdict alone does NOT promote — promotion is
    # an explicit team decision (FR-029, recorded by T028).
