"""Feature 020 / T033a / FR-007 / R-020.15: tests for the all-suppressed
disposition path that drives lazy PPStructureV3 construction.

The CPU-safe variant only proves the disposition seam returns ``"suppress"``
for every document in an all-`sufficient` corpus. The factory-not-called
assertion at the orchestrator level lives in the GPU variants
(`test_lazy_no_warmup`, `test_forced_construction_with_warmup`) which are
deferred per R-020.15.
"""

from __future__ import annotations

from typing import Any

import pytest

from ledgerlinc_ocr.preprocessing.pipeline import (
    decide_ocr_only_fallback_disposition,
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


@pytest.mark.gpu
@pytest.mark.skip(reason="GPU end-to-end; deferrable per R-020.15.")
def test_lazy_no_warmup(tmp_path: Any) -> None:
    """GPU end-to-end: `_ENGINE` stays None on an all-sufficient corpus."""


def test_all_sufficient_corpus_disposes_as_suppress() -> None:
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
@pytest.mark.skip(reason="GPU end-to-end; deferrable per R-020.15.")
def test_forced_construction_with_warmup(tmp_path: Any) -> None:
    """GPU end-to-end: `--gpu-warmup` forces PPStructureV3 construction."""
