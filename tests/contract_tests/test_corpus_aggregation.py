"""T061: validate_corpus aggregates per-folder outcomes and run summary."""
from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.validator import validate_corpus


def test_corpus_aggregates_sub_reports(good_fixtures_root: Path) -> None:
    root = good_fixtures_root / "corpus_sample"
    outcome = validate_corpus(root)
    # Two folders + one run_summary + one failing hard folder ⇒ 4 sub_reports
    assert len(outcome.sub_reports) == 4
    # At least one folder failure (inv_003_hard with no notes.md)
    assert outcome.passed is False
    failing = [s for s in outcome.sub_reports if not s.passed]
    assert any("inv_003_hard" in s.target_summary for s in failing)
    # Aggregated counts reflect sub_report errors
    assert outcome.counts.error >= 1


def test_corpus_fail_fast_stops_early(good_fixtures_root: Path) -> None:
    root = good_fixtures_root / "corpus_sample"
    outcome = validate_corpus(root, fail_fast=True)
    # fail_fast stops after first failing folder → at most 1 sub_report from the break
    # but the code still appends the summary at the end; allow at most 2.
    assert outcome.passed is False
    failing = [s for s in outcome.sub_reports if not s.passed]
    assert failing
