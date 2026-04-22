"""Contract tests — every evaluation_document.json and evaluation_run_summary.json
written by the evaluator must validate against its frozen schema."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from jsonschema import Draft202012Validator

from ledgerlinc_ocr.evaluator import evaluate_corpus, evaluate_document
from ledgerlinc_ocr.evaluator.schema import (
    load_evaluation_document_schema,
    load_evaluation_run_summary_schema,
)

_EVALUATOR_FIXTURES = (
    Path(__file__).resolve().parents[1] / "evaluator_tests" / "fixtures"
)


def test_all_match_output_validates_schema(tmp_path: Path) -> None:
    folder = tmp_path / "all_match"
    shutil.copytree(_EVALUATOR_FIXTURES / "all_match", folder)
    evaluate_document(folder)

    with (folder / "evaluation_document.json").open("r", encoding="utf-8") as fh:
        instance = json.load(fh)
    Draft202012Validator(load_evaluation_document_schema()).validate(instance)


def test_label_coverage_output_validates_schema(tmp_path: Path) -> None:
    folder = tmp_path / "label_coverage"
    shutil.copytree(_EVALUATOR_FIXTURES / "label_coverage", folder)
    evaluate_document(folder)

    with (folder / "evaluation_document.json").open("r", encoding="utf-8") as fh:
        instance = json.load(fh)
    Draft202012Validator(load_evaluation_document_schema()).validate(instance)


def test_run_summary_output_validates_schema(tmp_path: Path) -> None:
    root = tmp_path / "corpus_20"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root)
    evaluate_corpus(root)

    with (root / "evaluation_run_summary.json").open("r", encoding="utf-8") as fh:
        instance = json.load(fh)
    Draft202012Validator(load_evaluation_run_summary_schema()).validate(instance)


def test_corpus_end_to_end_artifact_set(tmp_path: Path) -> None:
    """T082: after one corpus run, every artifact is present and well-formed:
    per-folder evaluation_document.json validates; evaluation_run_summary.json
    validates; evaluation_run_summary.md has the expected section headings."""
    root = tmp_path / "corpus_20"
    shutil.copytree(_EVALUATOR_FIXTURES / "corpus_20", root)
    outcome = evaluate_corpus(root)
    assert outcome.ok is True

    doc_validator = Draft202012Validator(load_evaluation_document_schema())
    # Every per-doc folder has a schema-valid evaluation_document.json.
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        eval_path = folder / "evaluation_document.json"
        assert eval_path.is_file(), f"missing per-doc eval at {eval_path}"
        with eval_path.open("r", encoding="utf-8") as fh:
            instance = json.load(fh)
        doc_validator.validate(instance)

    # Run summary JSON validates against its frozen schema.
    summary_path = root / "evaluation_run_summary.json"
    with summary_path.open("r", encoding="utf-8") as fh:
        summary_instance = json.load(fh)
    Draft202012Validator(load_evaluation_run_summary_schema()).validate(summary_instance)

    # Markdown report renders the canonical sections per research.md §14.
    md_path = root / "evaluation_run_summary.md"
    assert md_path.is_file()
    md = md_path.read_text(encoding="utf-8")
    assert md.startswith("# Stage 1 Evaluation Run Summary\n")
    assert "## By difficulty" in md
    assert "## Failing documents" in md
    # Every required difficulty bucket row is present, in the fixed order.
    by_diff_block = md.split("## By difficulty", 1)[1].split(
        "## Failing documents", 1
    )[0]
    easy_pos = by_diff_block.index("| easy |")
    medium_pos = by_diff_block.index("| medium |")
    hard_pos = by_diff_block.index("| hard |")
    missing_pos = by_diff_block.index("| missing_name |")
    assert easy_pos < medium_pos < hard_pos < missing_pos
    assert md.endswith("\n")
