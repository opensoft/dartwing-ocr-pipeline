"""Feature 021 / T009 / FR-006: GPU end-to-end skip-fallback test.

Converted from the feature-020 R-020.15 placeholder. Exercises the
`sufficient`-decision skip-fallback path on `ppstructurev3@gpu`:

- Given a `sufficient` OCR-only document and `--evidence-gate-skip-fallback`,
- The pipeline run MUST:
  - increment `evidence_gate_suppressed_fallback_count` for that document,
  - NOT construct PPStructureV3 (lazy construction observable via the
    absence of `phase_timings.engine_init` and `phase_timings.warmup`
    keys on the per-document record).

Skipped on CPU by the root-conftest `pytest_collection_modifyitems` gate
when the FR-001 preflight state is not `ppstructurev3_init_succeeded`.

CPU-safe coverage of the same MI invariants lives in feature-020's
`test_evidence_gate_skip_fallback_borderline_cpu.py` and
`test_evidence_gate_recorded_over_final.py`.
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


def test_skip_fallback_sufficient_suppresses_ppstructurev3_gpu(tmp_path: Path) -> None:
    """A `sufficient`-eligible doc keeps the OCR-only output AND
    increments the suppression counter under `--evidence-gate-skip-fallback`."""
    doc_id = "inv_001_easy"
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

    # Precondition for the FR-006 scenario: the document MUST be classified
    # `sufficient`. If this fails, the corpus labeling has drifted; that is
    # a feature-020 / feature-006 concern, not an FR-006 failure.
    assert gate_doc.get("decision") == "sufficient", (
        f"corpus precondition failed: {doc_id} decision="
        f"{gate_doc.get('decision')!r}, expected 'sufficient'. "
        f"Skip-fallback semantics only apply to `sufficient` documents."
    )

    # FR-006: suppression counter increments for the sufficient doc.
    assert summary.get("evidence_gate_suppressed_fallback_count") == 1, (
        f"expected evidence_gate_suppressed_fallback_count == 1 (one "
        f"sufficient document suppressed); got "
        f"{summary.get('evidence_gate_suppressed_fallback_count')!r}"
    )

    # FR-008 corollary on a single-doc all-sufficient run: PPStructureV3
    # is lazily unconstructed (no engine_init, no warmup) when skip-fallback
    # suppresses the only document AND --gpu-warmup is NOT passed.
    keys = phase_keys(per_doc)
    assert "engine_init" not in keys, (
        f"FR-008 violation: phase_timings.engine_init present on a "
        f"suppressed-document run without --gpu-warmup; got phase keys "
        f"{sorted(keys)!r}"
    )
    assert "warmup" not in keys, (
        f"FR-008 violation: phase_timings.warmup present on a suppressed-"
        f"document run without --gpu-warmup; got phase keys "
        f"{sorted(keys)!r}"
    )
