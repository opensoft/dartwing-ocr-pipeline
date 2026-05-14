"""US2 corpus aggregator tests — covers AC#1–#8."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from dartwing_ocr.evaluator import evaluate_corpus, evaluate_document
from dartwing_ocr.evaluator.exceptions import EmptyCorpusError, SchemaValidationError
from dartwing_ocr.evaluator.scoring import SCORED_FIELDS
from dartwing_ocr.evaluator.schema import load_evaluation_run_summary_schema

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


def test_mid_corpus_hard_error_preserves_prior_writes(tmp_path: Path) -> None:
    """FR-020: when corpus eval aborts on a later folder, per-doc evaluations
    already written for earlier folders are preserved. Only the corpus-level
    summary is absent."""
    root = tmp_path / "mixed"
    root.mkdir()
    # Good folder comes first alphabetically so it is evaluated and its
    # evaluation_document.json is written before the bad folder raises.
    good_src = FIXTURES / "all_match"
    good_dst = root / "inv_aaa_good"
    shutil.copytree(good_src, good_dst)
    (good_dst / "evaluation_document.json").unlink(missing_ok=True)
    # Bad folder comes later; inv_bad_02's expected.json is unparsable.
    bad_src = FIXTURES / "corpus_bad_input" / "inv_bad_02"
    shutil.copytree(bad_src, root / "inv_zzz_bad")

    summary_path = root / "evaluation_run_summary.json"
    with pytest.raises(json.JSONDecodeError):
        evaluate_corpus(root)
    # Corpus-level summary is absent.
    assert not summary_path.exists()
    # Prior good folder's per-doc evaluation IS preserved.
    assert (good_dst / "evaluation_document.json").is_file()


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


def test_single_document_corpus(tmp_path: Path) -> None:
    """Edge case: N=1. Aggregation division-by-count still works at the lower
    boundary above the EmptyCorpusError guard."""
    root = tmp_path / "corpus_1"
    root.mkdir()
    shutil.copytree(FIXTURES / "all_match", root / "inv_only")
    outcome = evaluate_corpus(root)
    assert outcome.ok is True
    assert outcome.summary is not None
    assert outcome.summary.document_count == 1
    assert (
        sum(v.document_count for v in outcome.summary.by_difficulty.values()) == 1
    )


def test_two_document_corpus(tmp_path: Path) -> None:
    """Edge case: N=2, one passing and one failing. Ensures pass-rate
    arithmetic at tiny denominators is well-behaved."""
    root = tmp_path / "corpus_2"
    root.mkdir()
    shutil.copytree(FIXTURES / "all_match", root / "inv_pass")
    shutil.copytree(
        FIXTURES / "corpus_20" / "inv_corpus_missing_05_fail", root / "inv_fail"
    )
    outcome = evaluate_corpus(root)
    assert outcome.ok is True
    assert outcome.summary is not None
    assert outcome.summary.document_count == 2
    assert 0.0 <= outcome.summary.overall_metrics.overall_document_pass_rate <= 1.0


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


def test_refresh_forces_reevaluation_even_with_valid_cache(tmp_path: Path) -> None:
    """Fix §2 regression guard: evaluate_corpus(..., refresh=True) must ignore
    any on-disk evaluation_document.json and regenerate it, while the default
    (refresh=False) keeps trusting the cache as-is.

    Strategy:
      1. Populate the per-document cache by running in lazy mode.
      2. Mutate the cached artifact by flipping overall_passed false -> true
         (the fixture's all_match corpus scores as passing).
      3. refresh=False must preserve the mutation (stale cache reused).
      4. refresh=True must overwrite the mutation with freshly-computed values.
    """
    root = tmp_path / "corpus_refresh"
    root.mkdir()
    shutil.copytree(FIXTURES / "all_match", root / "inv_only")
    doc_folder = root / "inv_only"
    cache_path = doc_folder / "evaluation_document.json"

    # (1) Populate the cache.
    first = evaluate_corpus(root, lazy=True)
    assert first.ok is True
    assert cache_path.is_file()
    with cache_path.open("r", encoding="utf-8") as fh:
        cached = json.load(fh)
    assert cached["document_pass_fail"]["overall_passed"] is True

    # (2) Mutate the cache — flip overall_passed to false. The artifact stays
    # schema-valid because overall_passed is a plain boolean.
    cached["document_pass_fail"]["overall_passed"] = False
    with cache_path.open("w", encoding="utf-8") as fh:
        json.dump(cached, fh, indent=2)
    # Remove the run summary so we can uniquely observe each run's effect.
    (root / "evaluation_run_summary.json").unlink(missing_ok=True)
    (root / "evaluation_run_summary.md").unlink(missing_ok=True)

    # (3) refresh=False — the aggregator must reuse the mutated cache.
    stale = evaluate_corpus(root, lazy=True, refresh=False)
    assert stale.summary is not None
    stale_entry = next(
        d for d in stale.summary.documents if d.document_id == cached["document_id"]
    )
    assert stale_entry.overall_passed is False, (
        "refresh=False must reuse the on-disk (mutated) cache"
    )
    # The mutated cache file itself is untouched when reused.
    with cache_path.open("r", encoding="utf-8") as fh:
        after_stale = json.load(fh)
    assert after_stale["document_pass_fail"]["overall_passed"] is False

    # (4) refresh=True — the aggregator must recompute and overwrite.
    refreshed = evaluate_corpus(root, lazy=True, refresh=True)
    assert refreshed.summary is not None
    refreshed_entry = next(
        d for d in refreshed.summary.documents if d.document_id == cached["document_id"]
    )
    assert refreshed_entry.overall_passed is True, (
        "refresh=True must ignore the on-disk cache and recompute"
    )
    with cache_path.open("r", encoding="utf-8") as fh:
        after_refresh = json.load(fh)
    assert after_refresh["document_pass_fail"]["overall_passed"] is True


def test_evaluate_corpus_writes_only_inside_root(tmp_path: Path) -> None:
    """FR-025 writable-file scope: a successful `evaluate_corpus` call writes
    only `evaluation_run_summary.{json,md}` at the root and per-folder
    `evaluation_document.json` files inside each discovered doc folder."""
    root = _copy(FIXTURES / "corpus_20", tmp_path)
    before = {p for p in tmp_path.rglob("*") if p.is_file()}

    evaluate_corpus(root)

    new_files = {p for p in tmp_path.rglob("*") if p.is_file()} - before
    allowed = {
        root / "evaluation_run_summary.json",
        root / "evaluation_run_summary.md",
    }
    for folder in (p for p in root.iterdir() if p.is_dir()):
        allowed.add(folder / "evaluation_document.json")
    unexpected = new_files - allowed
    assert not unexpected, f"evaluate_corpus wrote unexpected files: {unexpected}"
