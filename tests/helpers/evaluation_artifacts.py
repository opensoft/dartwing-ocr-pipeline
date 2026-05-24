"""Shared test-data builders for ``evaluation_run_summary.json``-shaped dicts.

Extracted per Sonar duplication finding on PR #47 (2026-05-23): the
minimal ``evaluation_run_summary`` shell — top-level keys plus the
``by_difficulty`` skeleton, ``overall_metrics``, ``consensus_metrics``,
``by_field``, ``documents`` — was replicated identically across three
test files (``test_backward_compat_v1_2.py``,
``test_evaluation_run_summary_v1_3.py``,
``test_us3_evaluator_reports.py``), pushing duplicated-lines density to
4.7% (Sonar threshold 3%).

These builders are pure-Python dict constructors; no schema validation
or business logic — that lives in the call sites. Each call returns a
fresh, mutable dict so callers can layer overrides without affecting
other tests.
"""

from __future__ import annotations

from typing import Any


def build_empty_difficulty_stats() -> dict[str, dict[str, float | int]]:
    """Return a fresh ``by_difficulty`` dict with zeroed entries for all
    four difficulty buckets (easy / medium / hard / missing_name)."""
    return {
        difficulty: {
            "document_count": 0,
            "field_accuracy": 0.0,
            "overall_document_pass_rate": 0.0,
        }
        for difficulty in ("easy", "medium", "hard", "missing_name")
    }


def build_overall_metrics_all_pass() -> dict[str, float]:
    """Return a fresh ``overall_metrics`` dict with every rate at 1.0."""
    return {
        "field_accuracy": 1.0,
        "vendor_identity_pass_rate": 1.0,
        "review_routing_pass_rate": 1.0,
        "overall_document_pass_rate": 1.0,
    }


def build_consensus_metrics_zero() -> dict[str, int]:
    """Return a fresh ``consensus_metrics`` dict with all counters at 0."""
    return {
        "single_voter_baseline_runs": 0,
        "majority_vote_documents": 0,
        "split_decision_documents": 0,
    }


def build_minimal_evaluation_run_summary(
    *,
    contract_set_version: str = "1.3.0",
    run_id: str = "run_test",
    **overrides: Any,
) -> dict[str, Any]:
    """Return a fresh minimal ``evaluation_run_summary.json``-shaped dict.

    Args:
        contract_set_version: The ``contract_set_version`` field value
            (default ``"1.3.0"``; callers testing backward-compat pass
            ``"1.2.0"``).
        run_id: The ``run_id`` field value (default ``"run_test"``;
            backward-compat tests typically pass ``"run_legacy"``).
        **overrides: Any additional keys (or replacements for existing
            keys) to merge into the returned dict. Useful for testing
            the additive v1.3.0 fields (``semantic_table_quality_metrics``,
            ``semantic_document_statuses``) by passing them as kwargs.

    Returns:
        A fresh dict; callers may mutate freely.
    """
    base: dict[str, Any] = {
        "contract_set_version": contract_set_version,
        "run_id": run_id,
        "document_count": 0,
        "overall_metrics": build_overall_metrics_all_pass(),
        "consensus_metrics": build_consensus_metrics_zero(),
        "by_difficulty": build_empty_difficulty_stats(),
        "by_field": {},
        "documents": [],
    }
    base.update(overrides)
    return base


def build_pre_feature_run_summary() -> dict[str, Any]:
    """Return a fresh v1.2.0-shaped ``evaluation_run_summary.json`` dict.

    No semantic fields (FR-019 / Q43 backward-compat). Convenience
    wrapper around :func:`build_minimal_evaluation_run_summary` with
    ``contract_set_version="1.2.0"`` and ``run_id="run_legacy"``.
    """
    return build_minimal_evaluation_run_summary(
        contract_set_version="1.2.0",
        run_id="run_legacy",
    )
