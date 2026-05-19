"""Feature 021 / T011 / FR-008 + FR-009: tests for the all-suppressed
disposition path that drives lazy PPStructureV3 construction.

This file holds three tests:

1. ``test_all_sufficient_corpus_disposes_as_suppress`` — CPU-safe seam
   test (inherited from feature 020 T033a / R-020.15). Proves the
   disposition function returns ``"suppress"`` for every doc in an all-
   sufficient corpus.
2. ``test_lazy_no_warmup`` — feature 021 / T011a / FR-008. GPU end-to-end:
   an all-sufficient corpus + `--evidence-gate-skip-fallback` + NO
   `--gpu-warmup` keeps PPStructureV3 unconstructed (observable via the
   absence of `phase_timings.engine_init` and `phase_timings.warmup`
   on EVERY per-doc record).
3. ``test_forced_construction_with_warmup`` — feature 021 / T011b / FR-009.
   GPU end-to-end: same corpus + `--gpu-warmup` set forces PPStructureV3
   construction (warmup phase key present), even though every document
   is later suppressed (the explicit operator trade-off per FR-009).

Tests 2 and 3 are skipped on CPU by the root-conftest
``pytest_collection_modifyitems`` gate. Test 1 runs on CPU.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dartwing_ocr.preprocessing.pipeline import (
    decide_ocr_only_fallback_disposition,
)
from tests.pipeline_tests.gpu_helpers import (
    extract_run_summary,
    find_evidence_gate_record,
    find_per_document_record,
    invoke_pipeline,
    phase_keys,
    setup_scratch_corpus,
)


def _sufficient_pages() -> list[dict[str, Any]]:
    return [
        {
            "height": 1000,
            "blocks": [
                {
                    "bbox": [10, 20, 200, 60],
                    "text": "Acme Widgets LLC",
                    "confidence": 0.92,
                },
                {
                    "bbox": [10, 70, 400, 90],
                    "text": "1234 Main Street Suite 200 Anytown CA 94000",
                    "confidence": 0.90,
                },
                {
                    "bbox": [10, 110, 400, 130],
                    "text": "Vendor Tax ID 12-3456789 contact",
                    "confidence": 0.88,
                },
            ],
        }
    ]


def test_all_sufficient_corpus_disposes_as_suppress() -> None:
    """CPU-safe seam: disposition function returns 'suppress' for every doc
    in an all-sufficient corpus when skip-fallback is opted in."""
    documents = [
        ("inv_001_easy", _sufficient_pages()),
        ("inv_002_easy", _sufficient_pages()),
        ("inv_003_easy", _sufficient_pages()),
    ]
    for doc_id, pages in documents:
        disposition, candidate_decision = decide_ocr_only_fallback_disposition(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=True,
            opt_in_active=True,
            candidate_pages=pages,
        )
        assert disposition == "suppress", (
            f"{doc_id}: expected suppress; got {disposition=}, {candidate_decision=}"
        )
        assert candidate_decision == "sufficient", (
            f"{doc_id}: expected sufficient; got {candidate_decision!r}"
        )


@pytest.mark.gpu
def test_lazy_no_warmup(tmp_path: Path) -> None:
    """FR-008: all-sufficient corpus + no `--gpu-warmup` keeps PPStructureV3
    unconstructed for every document."""
    # inv_001_easy and inv_002_easy are the two easy-tier documents that
    # the FR-011 benchmark subset uses as `sufficient` representatives.
    doc_ids = ["inv_001_easy", "inv_002_easy"]
    documents_file, _ = setup_scratch_corpus(scratch_root=tmp_path, doc_ids=doc_ids)

    result = invoke_pipeline(
        documents_file=documents_file,
        extra_flags=["--evidence-gate-skip-fallback"],
    )

    assert result.returncode == 0, (
        f"pipeline failed (exit {result.returncode}); stderr=\n{result.stderr}"
    )

    summary = extract_run_summary(result.stdout)

    # Precondition: every doc is `sufficient`. If not, this scenario does
    # not apply; the corpus has drifted and needs re-labeling.
    for doc_id in doc_ids:
        gate_doc = find_evidence_gate_record(summary, doc_id)
        assert gate_doc.get("decision") == "sufficient", (
            f"corpus precondition failed: {doc_id} decision="
            f"{gate_doc.get('decision')!r}, expected 'sufficient'."
        )

    # FR-008: every doc suppressed.
    assert summary.get("evidence_gate_suppressed_fallback_count") == len(doc_ids), (
        f"expected evidence_gate_suppressed_fallback_count == {len(doc_ids)} "
        f"(all-sufficient corpus, all suppressed); got "
        f"{summary.get('evidence_gate_suppressed_fallback_count')!r}"
    )

    # FR-008 core assertion: engine_init AND warmup absent on EVERY per-doc
    # record (PPStructureV3 was never constructed for this run).
    for doc_id in doc_ids:
        per_doc = find_per_document_record(summary, doc_id)
        keys = phase_keys(per_doc)
        assert "engine_init" not in keys, (
            f"FR-008 violation: phase_timings.engine_init present on {doc_id} "
            f"during an all-suppressed run without `--gpu-warmup`; "
            f"phase keys: {sorted(keys)!r}"
        )
        assert "warmup" not in keys, (
            f"FR-008 violation: phase_timings.warmup present on {doc_id} "
            f"during an all-suppressed run without `--gpu-warmup`; "
            f"phase keys: {sorted(keys)!r}"
        )


@pytest.mark.gpu
def test_forced_construction_with_warmup(tmp_path: Path) -> None:
    """FR-009: same all-sufficient corpus + `--gpu-warmup` set forces
    PPStructureV3 construction (warmup phase key present), even though
    every document is later suppressed."""
    doc_ids = ["inv_001_easy", "inv_002_easy"]
    documents_file, _ = setup_scratch_corpus(scratch_root=tmp_path, doc_ids=doc_ids)

    result = invoke_pipeline(
        documents_file=documents_file,
        extra_flags=["--evidence-gate-skip-fallback", "--gpu-warmup"],
    )

    assert result.returncode == 0, (
        f"pipeline failed (exit {result.returncode}); stderr=\n{result.stderr}"
    )

    summary = extract_run_summary(result.stdout)

    # Precondition: every doc is `sufficient` (mirrors test_lazy_no_warmup).
    for doc_id in doc_ids:
        gate_doc = find_evidence_gate_record(summary, doc_id)
        assert gate_doc.get("decision") == "sufficient", (
            f"corpus precondition failed: {doc_id} decision="
            f"{gate_doc.get('decision')!r}, expected 'sufficient'."
        )

    # FR-009: every doc still suppressed (skip-fallback is independent of
    # warmup; warmup is the explicit operator trade-off, not a suppression
    # override).
    assert summary.get("evidence_gate_suppressed_fallback_count") == len(doc_ids), (
        f"expected evidence_gate_suppressed_fallback_count == {len(doc_ids)}; "
        f"got {summary.get('evidence_gate_suppressed_fallback_count')!r}"
    )

    # FR-009 core assertion: warmup phase key MUST appear somewhere — the
    # `--gpu-warmup` flag forces PPStructureV3 construction. The warmup
    # timing is recorded once per run, not once per document, so it appears
    # on at least one (typically the first) per-doc record.
    saw_warmup = False
    saw_engine_init = False
    for doc_id in doc_ids:
        per_doc = find_per_document_record(summary, doc_id)
        keys = phase_keys(per_doc)
        if "warmup" in keys:
            saw_warmup = True
        if "engine_init" in keys:
            saw_engine_init = True

    assert saw_warmup, (
        "FR-009 violation: `--gpu-warmup` was passed but phase_timings.warmup "
        "is absent from every per-doc record (PPStructureV3 was not constructed). "
        "This contradicts the explicit operator trade-off of the warmup flag."
    )
    # Engine init typically accompanies a warmup run (engine has to be
    # constructed before warmup can run). Multi-agent-review LOW-5 fix:
    # this is documented as a soft observation ("warn but do not fail —
    # feature 016 may amortize engine_init across runs") but used to call
    # `pytest.fail`, contradicting the comment. Switched to `warnings.warn`
    # so the test still surfaces the amortization signal without failing
    # FR-009 coverage when feature 016's MIOpen cache reuse legitimately
    # elides the engine_init phase entry on warm runs.
    if not saw_engine_init:
        import warnings

        warnings.warn(
            "FR-009 observation: phase_timings.engine_init absent even though "
            "warmup forced PPStructureV3 construction. Feature 016 amortization "
            "is the expected explanation; if it isn't, investigate.",
            stacklevel=2,
        )
