"""Feature 021 / T010 / FR-007: GPU end-to-end borderline-fallback test.

Converted from the feature-020 R-020.15 placeholder. Exercises the
`borderline`-decision (and by extension `insufficient`) path on
`ppstructurev3@gpu` when `--evidence-gate-skip-fallback` is set:

- Given a `borderline` or `insufficient` document and
  `--evidence-gate-skip-fallback`,
- The pipeline run MUST:
  - execute PPStructureV3 fallback for that document (observable via
    presence of `phase_timings.engine_init` and/or `phase_timings.warmup`
    on the per-document record),
  - NOT increment `evidence_gate_suppressed_fallback_count` for that doc
    (the decision table compliance — skip-fallback only suppresses
    `sufficient` documents per FR-006/FR-007).

Skipped on CPU by the root-conftest `pytest_collection_modifyitems` gate.

CPU-safe coverage of the same MI-11 invariant lives in
`test_evidence_gate_skip_fallback_borderline_cpu.py` (feature 020 T034a).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.pipeline_tests.gpu_helpers import (
    extract_run_summary,
    find_evidence_gate_record,
    find_per_document_record,
    invoke_pipeline,
    phase_keys,
    setup_scratch_corpus,
)

pytestmark = pytest.mark.gpu


def test_skip_fallback_borderline_runs_fallback_gpu(tmp_path: Path) -> None:
    """A `borderline` or `insufficient` candidate runs PPStructureV3 fallback
    even under `--evidence-gate-skip-fallback`; the suppression counter does
    NOT increment for that document."""
    # `inv_011_hard` is selected because hard-difficulty documents typically
    # fall short of one or more sufficiency signals (low density, missing
    # business suffix, or ambiguous tax-id-shape) and land as `borderline`
    # or `insufficient` under the v1 decision table. If this document is
    # ever relabeled to `sufficient`, the precondition assertion will
    # flag it and the operator can swap to another hard-difficulty doc.
    doc_id = "inv_011_hard"
    documents_file, _ = setup_scratch_corpus(scratch_root=tmp_path, doc_ids=[doc_id])

    result = invoke_pipeline(
        documents_file=documents_file,
        extra_flags=["--evidence-gate-skip-fallback"],
    )

    assert result.returncode == 0, (
        f"pipeline failed (exit {result.returncode}); stderr=\n{result.stderr}"
    )

    summary = extract_run_summary(result.stdout)
    gate_doc = find_evidence_gate_record(summary, doc_id)
    per_doc = find_per_document_record(summary, doc_id)

    # Precondition for the FR-007 scenario: the document MUST be classified
    # `borderline` or `insufficient`. If it's `sufficient`, this test is
    # exercising the wrong scenario; swap the doc_id rather than weakening
    # the assertion.
    decision = gate_doc.get("decision")
    assert decision in {"borderline", "insufficient"}, (
        f"corpus precondition failed: {doc_id} decision={decision!r}, "
        f"expected 'borderline' or 'insufficient'. "
        f"Skip-fallback fallback semantics only apply to non-sufficient docs."
    )

    # FR-007: suppression counter does NOT increment for the non-sufficient doc.
    assert summary.get("evidence_gate_suppressed_fallback_count") == 0, (
        f"FR-007 violation: evidence_gate_suppressed_fallback_count incremented "
        f"for a {decision!r} document (skip-fallback should only suppress "
        f"`sufficient` documents); got "
        f"{summary.get('evidence_gate_suppressed_fallback_count')!r}"
    )

    # FR-007 corollary: PPStructureV3 fallback IS executed, observable via
    # phase_timings.engine_init (or warmup) presence on the per-doc record.
    keys = phase_keys(per_doc)
    assert "engine_init" in keys or "warmup" in keys, (
        f"FR-007 violation: PPStructureV3 was not constructed for a "
        f"{decision!r} document (expected fallback execution). "
        f"phase_timings keys present: {sorted(keys)!r}"
    )
