"""US5 run-report tests — AC#1–#4 and FR-021."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dartwing_ocr.evaluator import evaluate_corpus
from dartwing_ocr.evaluator.compare import FieldResult
from dartwing_ocr.evaluator.corpus import (
    ConsensusMetrics,
    DifficultyStats,
    DocumentListEntry,
    OverallMetrics,
    RunSummary,
)
from dartwing_ocr.evaluator.document import DocumentEvaluation
from dartwing_ocr.evaluator.gates import DocumentPassFail
from dartwing_ocr.evaluator.report import render_run_summary, summarize_failure
from dartwing_ocr.evaluator.scoring import (
    CONTRACT_SET_VERSION,
    ComparisonSummary,
    ResultLabel,
    SCORED_FIELDS,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _copy(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def test_headline_metrics(tmp_path: Path) -> None:
    """US5 AC#1: all four headline metrics appear with numeric values."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    summary = outcome.summary
    assert summary is not None
    ev_tuple = tuple(o.evaluation for o in outcome.per_document if o.evaluation)

    md = render_run_summary(summary, document_evaluations=ev_tuple)

    assert f"- Run ID: {summary.run_id}" in md
    assert f"- Document count: {summary.document_count}" in md
    assert (
        f"- Overall pass rate: {summary.overall_metrics.overall_document_pass_rate:.3f}"
        in md
    )
    assert (
        f"- Vendor identity pass rate: {summary.overall_metrics.vendor_identity_pass_rate:.3f}"
        in md
    )
    assert (
        f"- Review routing pass rate: {summary.overall_metrics.review_routing_pass_rate:.3f}"
        in md
    )
    assert (
        f"- Field accuracy: {summary.overall_metrics.field_accuracy:.3f}" in md
    )

    # By-difficulty table is rendered in the fixed order.
    by_diff_index = md.index("## By difficulty")
    failing_index = md.index("## Failing documents")
    table_block = md[by_diff_index:failing_index]
    for key in ("easy", "medium", "hard", "missing_name"):
        assert f"| {key} |" in table_block
    assert table_block.index("| easy |") < table_block.index("| medium |")
    assert table_block.index("| medium |") < table_block.index("| hard |")
    assert table_block.index("| hard |") < table_block.index("| missing_name |")


def test_failing_documents_list(tmp_path: Path) -> None:
    """US5 AC#2: each failing-doc line includes id, difficulty bucket, and reason."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    summary = outcome.summary
    assert summary is not None
    ev_tuple = tuple(o.evaluation for o in outcome.per_document if o.evaluation)
    failing_evs = [ev for ev in ev_tuple if not ev.document_pass_fail.overall_passed]
    assert failing_evs, "corpus_20 is expected to contain at least one failing document"

    md = render_run_summary(summary, document_evaluations=ev_tuple)
    failing_section = md.split("## Failing documents", 1)[1]

    for ev in failing_evs:
        reason = summarize_failure(ev)
        expected_line = f"- {ev.document_id} ({ev.difficulty}) — {reason}"
        assert expected_line in failing_section, (
            f"missing failing-doc line for {ev.document_id}: {expected_line!r}\n"
            f"in:\n{failing_section}"
        )


def test_zero_failures_fallback(tmp_path: Path) -> None:
    """US5 AC#3: all-passing corpus renders the italic fallback sentinel."""
    root = _copy(FIXTURES / "corpus_prebuilt_3", tmp_path)
    outcome = evaluate_corpus(root, lazy=False)
    summary = outcome.summary
    assert summary is not None
    ev_tuple = tuple(o.evaluation for o in outcome.per_document if o.evaluation)
    # Precondition: this fixture is indeed all-passing.
    assert all(d.overall_passed for d in summary.documents)

    md = render_run_summary(summary, document_evaluations=ev_tuple)

    failing_section = md.split("## Failing documents", 1)[1]
    assert "_All documents passed._" in failing_section
    # No bulleted failing-doc entries.
    assert "\n- " not in failing_section.replace(
        "_All documents passed._", ""
    ).split("\n", 2)[-1]


def test_deterministic_ordering(tmp_path: Path) -> None:
    """US5 AC#4: byte-identical output from the same RunSummary; failing docs
    sorted ascending by document_id."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    summary = outcome.summary
    assert summary is not None
    ev_tuple = tuple(o.evaluation for o in outcome.per_document if o.evaluation)

    md_a = render_run_summary(summary, document_evaluations=ev_tuple)
    md_b = render_run_summary(summary, document_evaluations=ev_tuple)
    assert md_a == md_b

    # Failing-doc lines sorted asc by document_id.
    failing_section = md_a.split("## Failing documents", 1)[1]
    failing_ids = [
        line[len("- ") :].split(" (", 1)[0]
        for line in failing_section.splitlines()
        if line.startswith("- ")
    ]
    assert failing_ids == sorted(failing_ids)


def test_md_file_matches_stdout(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """FR-021: on-disk `evaluation_run_summary.md` equals CLI stdout byte-for-byte."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)

    # Run the CLI corpus handler end-to-end (writes MD + prints to stdout).
    from dartwing_ocr.evaluator.cli import main

    exit_code = main(["evaluate", "corpus", str(root)])
    assert exit_code == 0

    captured = capsys.readouterr()
    md_path = root / "evaluation_run_summary.md"
    assert md_path.is_file()
    on_disk = md_path.read_text(encoding="utf-8")
    assert captured.out == on_disk


def test_score_below_threshold_fallback(tmp_path: Path) -> None:
    """`summarize_failure` falls back to `document_score x.xxx below threshold`
    when a document fails the overall gate but no field_result is in a failing
    label. Covers the fallback branch in `report.py` lines 42-44."""
    # Build a DocumentEvaluation where every field_result is MATCH (so no
    # failing entries are listed) yet `overall_passed=False`. The weighted
    # score from all-MATCH is 1.0, which would normally pass — we construct
    # this state to exercise the fallback branch when no field_result
    # surfaces a failing label.
    field_results = tuple(
        FieldResult(
            field_name=name,
            expected="x",
            actual="x",
            result=ResultLabel.MATCH,
        )
        for name in SCORED_FIELDS
    )
    summary = ComparisonSummary(
        applicable_field_count=len(SCORED_FIELDS),
        matched_field_count=len(SCORED_FIELDS),
        mismatched_field_count=0,
        missing_prediction_count=0,
        unexpected_prediction_count=0,
        field_accuracy=1.0,
    )
    pass_fail = DocumentPassFail(
        vendor_identity_passed=False,
        review_routing_passed=True,
        overall_passed=False,
    )
    # Use an arbitrary sub-threshold document_score to assert the formatted
    # fallback sentence is rendered verbatim.
    doc_score = 0.732
    ev = DocumentEvaluation(
        contract_set_version=CONTRACT_SET_VERSION,
        document_id="inv_999_easy",
        difficulty="easy",
        challenge_tags=(),
        comparison_summary=summary,
        document_pass_fail=pass_fail,
        field_results=field_results,
        notes=(),
        document_score=doc_score,
        folder_path=tmp_path / "inv_999_easy",
    )

    # Direct unit on summarize_failure.
    assert summarize_failure(ev) == f"document_score {doc_score:.3f} below threshold"

    # And the fallback phrase reaches the rendered run summary.
    run_summary = RunSummary(
        contract_set_version=CONTRACT_SET_VERSION,
        run_id="run_test",
        pipeline_version=None,
        policy_version=None,
        document_count=1,
        overall_metrics=OverallMetrics(
            field_accuracy=1.0,
            vendor_identity_pass_rate=0.0,
            review_routing_pass_rate=1.0,
            overall_document_pass_rate=0.0,
        ),
        consensus_metrics=ConsensusMetrics(
            single_voter_baseline_runs=1,
            majority_vote_documents=0,
            split_decision_documents=0,
        ),
        by_difficulty={
            "easy": DifficultyStats(
                document_count=1,
                field_accuracy=1.0,
                overall_document_pass_rate=0.0,
            ),
            "medium": DifficultyStats(0, 0.0, 0.0),
            "hard": DifficultyStats(0, 0.0, 0.0),
            "missing_name": DifficultyStats(0, 0.0, 0.0),
        },
        by_field=dict.fromkeys(SCORED_FIELDS, 1.0),
        documents=(
            DocumentListEntry(
                document_id="inv_999_easy",
                overall_passed=False,
                field_accuracy=1.0,
            ),
        ),
    )
    md = render_run_summary(run_summary, document_evaluations=(ev,))
    assert f"document_score {doc_score:.3f} below threshold" in md
