"""US2 corpus aggregator tests — covers AC#1–#8."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ledgerlinc_ocr.evaluator import evaluate_corpus, evaluate_document
from ledgerlinc_ocr.evaluator.exceptions import EmptyCorpusError, SchemaValidationError
from ledgerlinc_ocr.evaluator.scoring import SCORED_FIELDS
from ledgerlinc_ocr.evaluator.schema import load_evaluation_run_summary_schema

FIXTURES = Path(__file__).parent / "fixtures"


def _copy(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    return dst


def test_summary_writes_and_validates_schema(tmp_path: Path) -> None:
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    summary_path = root / "evaluation_run_summary.json"
    assert summary_path.exists()
    with summary_path.open("r", encoding="utf-8") as fh:
        instance = json.load(fh)
    Draft202012Validator(load_evaluation_run_summary_schema()).validate(instance)
    assert outcome.summary is not None
    assert outcome.summary.document_count == 20


def test_overall_metrics_match_hand_computed(tmp_path: Path) -> None:
    """AC#1: hand-compute overall metrics independently and compare."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    s = outcome.summary
    assert s is not None

    # Independently evaluate each folder and reduce
    per_doc = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder / "expected.json").is_file():
            continue
        result = evaluate_document(folder)
        per_doc.append(result.evaluation)

    count = len(per_doc)
    exp_field = round(
        sum(ev.comparison_summary.field_accuracy for ev in per_doc) / count, 6
    )
    exp_vi = round(
        sum(1 for ev in per_doc if ev.document_pass_fail.vendor_identity_passed) / count,
        6,
    )
    exp_rr = round(
        sum(1 for ev in per_doc if ev.document_pass_fail.review_routing_passed) / count,
        6,
    )
    exp_overall = round(
        sum(1 for ev in per_doc if ev.document_pass_fail.overall_passed) / count, 6
    )

    assert s.overall_metrics.field_accuracy == pytest.approx(exp_field, abs=1e-6)
    assert s.overall_metrics.vendor_identity_pass_rate == pytest.approx(exp_vi, abs=1e-6)
    assert s.overall_metrics.review_routing_pass_rate == pytest.approx(exp_rr, abs=1e-6)
    assert s.overall_metrics.overall_document_pass_rate == pytest.approx(
        exp_overall, abs=1e-6
    )


def test_by_difficulty_keyset_and_counts(tmp_path: Path) -> None:
    """AC#3: exactly {easy, medium, hard, missing_name}; counts sum to document_count."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    s = outcome.summary
    assert s is not None
    assert tuple(s.by_difficulty.keys()) == ("easy", "medium", "hard", "missing_name")
    assert (
        sum(v.document_count for v in s.by_difficulty.values()) == s.document_count
    )


def test_by_field_dotted_keys_and_range(tmp_path: Path) -> None:
    """AC#4: dotted keys + [0.0, 1.0] range."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    s = outcome.summary
    assert s is not None
    assert set(s.by_field.keys()) == set(SCORED_FIELDS)
    for key, value in s.by_field.items():
        assert 0.0 <= value <= 1.0, f"{key} out of range: {value}"


def test_consensus_metrics_single_voter_baseline(tmp_path: Path) -> None:
    """AC#5: stage-1 single-voter baseline; ensemble optionals omitted."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    s = outcome.summary
    assert s is not None
    cm = s.consensus_metrics
    assert cm.single_voter_baseline_runs == s.document_count
    assert cm.majority_vote_documents == 0
    assert cm.split_decision_documents == 0
    assert cm.unanimous_field_rate is None
    assert cm.two_of_three_majority_rate is None
    assert cm.split_decision_rate is None


def test_documents_sorted_ascending(tmp_path: Path) -> None:
    """AC#6: documents[] sorted by document_id ascending."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    s = outcome.summary
    assert s is not None
    ids = [d.document_id for d in s.documents]
    assert ids == sorted(ids)
    assert len(ids) == s.document_count


def test_lazy_eval(tmp_path: Path) -> None:
    """AC#8 lazy path: starts with no evaluation_document.json per folder;
    after corpus eval each folder has a valid one + run summary exists."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    # Sanity: fixture starts without per-doc evaluations
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        assert not (folder / "evaluation_document.json").exists()

    outcome = evaluate_corpus(root)
    assert outcome.ok is True
    assert (root / "evaluation_run_summary.json").exists()
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder / "expected.json").is_file():
            continue
        assert (folder / "evaluation_document.json").exists()


def test_hard_error_no_partial_summary(tmp_path: Path) -> None:
    """AC#8 abort path: a hard error surfaces without writing summary."""
    root = _copy(FIXTURES / "corpus_bad_input", tmp_path)
    summary_path = root / "evaluation_run_summary.json"
    with pytest.raises(json.JSONDecodeError):
        evaluate_corpus(root)
    assert not summary_path.exists()


def test_no_lazy_mode_passes_on_prebuilt(tmp_path: Path) -> None:
    """--no-lazy completes against a corpus that already has evaluation_document.json."""
    root = _copy(FIXTURES / "corpus_prebuilt_3", tmp_path)
    outcome = evaluate_corpus(root, lazy=False)
    assert outcome.ok is True
    assert outcome.summary is not None
    assert outcome.summary.document_count == 3


def test_no_lazy_mode_hard_fails_on_missing_evaluation(tmp_path: Path) -> None:
    """--no-lazy hard-fails when any folder is missing evaluation_document.json."""
    root = _copy(FIXTURES / "corpus_prebuilt_3", tmp_path)
    # Delete one folder's pre-built evaluation to simulate a missing artifact
    missing = root / "inv_corpus_easy_02" / "evaluation_document.json"
    missing.unlink()
    summary_path = root / "evaluation_run_summary.json"
    with pytest.raises(FileNotFoundError):
        evaluate_corpus(root, lazy=False)
    assert not summary_path.exists()


def test_empty_corpus_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(EmptyCorpusError):
        evaluate_corpus(empty)


def test_missing_name_bucket_pass_rate(tmp_path: Path) -> None:
    """US4 AC#4: the `missing_name` bucket counts invariant violations as failing.

    `corpus_20/inv_corpus_missing_05_fail` has `review_reason = "low_confidence"`
    (not the canonical `"company_name_inferred"`); its overall_passed must be
    false and the bucket pass rate must drop below 1.0.
    """
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    outcome = evaluate_corpus(root)
    s = outcome.summary
    assert s is not None
    bucket = s.by_difficulty["missing_name"]
    assert bucket.document_count == 5
    assert bucket.overall_document_pass_rate < 1.0
    # Specifically verify the violating doc failed overall.
    violating = next(
        d for d in s.documents if d.document_id == "inv_corpus_missing_05_fail"
    )
    assert violating.overall_passed is False
