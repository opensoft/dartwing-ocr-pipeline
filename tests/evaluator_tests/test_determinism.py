"""Determinism tests — byte-identical output across runs (SC-005)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ledgerlinc_ocr.evaluator import evaluate_corpus, evaluate_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_document_byte_identical(tmp_path: Path) -> None:
    """US1 AC#8: per-document eval has no run_id — output must be byte-identical across runs."""
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    shutil.copytree(FIXTURES / "all_match", run_a)
    shutil.copytree(FIXTURES / "all_match", run_b)

    evaluate_document(run_a)
    evaluate_document(run_b)

    bytes_a = (run_a / "evaluation_document.json").read_bytes()
    bytes_b = (run_b / "evaluation_document.json").read_bytes()
    assert bytes_a == bytes_b


def test_run_summary_byte_identical(tmp_path: Path) -> None:
    """US2: run summary must be byte-identical modulo `run_id` (quickstart §5, SC-005)."""
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    shutil.copytree(FIXTURES / "corpus_20", run_a)
    shutil.copytree(FIXTURES / "corpus_20", run_b)

    evaluate_corpus(run_a)
    evaluate_corpus(run_b)

    with (run_a / "evaluation_run_summary.json").open("r", encoding="utf-8") as fh:
        a = json.load(fh)
    with (run_b / "evaluation_run_summary.json").open("r", encoding="utf-8") as fh:
        b = json.load(fh)
    a.pop("run_id")
    b.pop("run_id")
    assert a == b
