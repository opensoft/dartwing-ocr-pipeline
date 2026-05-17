"""T087: SC-001 / SC-002 wall-clock performance gates."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from dartwing_ocr.evaluator import evaluate_corpus, evaluate_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_single_document_under_one_second(tmp_path: Path) -> None:
    """SC-001: one `evaluate_document` call completes in <= 1.0 s wall-clock."""
    folder = tmp_path / "all_match"
    shutil.copytree(FIXTURES / "all_match", folder)
    start = time.perf_counter()
    evaluate_document(folder)
    elapsed = time.perf_counter() - start
    assert elapsed <= 1.0, f"single-doc eval took {elapsed:.3f}s (budget 1.0 s)"


def test_corpus_twenty_under_five_seconds(tmp_path: Path) -> None:
    """SC-002: `evaluate_corpus` on `corpus_20/` (lazy, cold start).

    Spec contract is <= 5.0 s; local gate is tighter (1.5 s) so early
    regressions are caught before they approach the contract limit. Relax
    to 5.0 s in CI if developer hardware proves too noisy."""
    root = tmp_path / "corpus_20"
    shutil.copytree(FIXTURES / "corpus_20", root)
    start = time.perf_counter()
    evaluate_corpus(root)
    elapsed = time.perf_counter() - start
    assert elapsed <= 1.5, (
        f"corpus_20 eval took {elapsed:.3f}s (local gate 1.5 s, SC-002 5.0 s)"
    )
