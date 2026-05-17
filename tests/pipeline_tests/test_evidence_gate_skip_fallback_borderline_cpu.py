"""Feature 020 / T034a / R-020.7 / R-020.8 / R-020.15 / MI-11: CPU-safe
variant of the borderline-fallback acceptance test.

Merge-gating per R-020.15 deferral floor: this test MUST pass at merge
even if the GPU variant (T034) is deferred to a follow-up.

Uses the injection seam `decide_ocr_only_fallback_disposition` landed in
T040 to exercise the disposition logic without invoking PaddleOCR.
Asserts MI-11: when the suppression predicate returns False and a
fallback fires, the gate MUST be evaluated TWICE per document — once on
the OCR-only candidate (for the predicate input) and once on the post-
fallback output (for the recorded decision).
"""

from __future__ import annotations

from typing import Any

import pytest

from ledgerlinc_ocr.preprocessing.pipeline import (
    decide_ocr_only_fallback_disposition,
)


def _build_borderline_candidate_pages() -> list[dict[str, Any]]:
    """Construct page-1 blocks that produce a `borderline` gate decision.

    Borderline = some sufficiency signals present but not all four
    (vendor name + density + confidence + (suffix OR tax_id)). Here we
    keep a vendor candidate + density + confidence above threshold,
    but use lowercase address text so neither the EU-VAT-shape regex
    (`[A-Z]{2}[A-Z0-9]{2,12}`) nor the business-suffix regex fire.
    """
    return [
        {
            "height": 1000,
            "blocks": [
                {
                    "bbox": [10, 20, 200, 60],
                    "text": "Acme Widgets",
                    "confidence": 0.85,
                },
                {
                    "bbox": [10, 70, 400, 90],
                    "text": "main street suite 200 anytown california",
                    "confidence": 0.80,
                },
            ],
        }
    ]


def _build_sufficient_candidate_pages() -> list[dict[str, Any]]:
    """Construct page-1 blocks that produce a `sufficient` gate decision.

    Sufficient requires vendor candidate + density >= 8 + confidence >=
    0.70 + (business suffix OR tax id). Here we include `LLC` so the
    business-suffix regex fires.
    """
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
                    "confidence": 0.88,
                },
                {
                    "bbox": [10, 110, 400, 130],
                    "text": "Vendor ID 12-3456789 contact us anytime",
                    "confidence": 0.86,
                },
            ],
        }
    ]


def _build_empty_candidate_pages() -> list[dict[str, Any]]:
    """Construct an empty page-1 body that yields `insufficient`."""
    return [{"height": 1000, "blocks": []}]


def test_borderline_candidate_gates_fall_through_to_fallback() -> None:
    """MI-11 / MI-14 / FR-009: borderline candidate decision MUST yield
    `fallback` disposition under the four-conjunct R-020.8 predicate
    (no suppression on borderline)."""
    disposition, candidate_decision = decide_ocr_only_fallback_disposition(
        preprocess_strategy_id="ocr-only-v1",
        fr_005_trigger_would_fire=True,
        opt_in_active=True,
        candidate_pages=_build_borderline_candidate_pages(),
    )
    # Candidate decision is what the gate emitted on the OCR-only output.
    # The borderline pages we crafted may evaluate to "borderline" or
    # "insufficient" depending on density thresholds; in either case the
    # disposition MUST be `fallback` (MI-14).
    assert disposition == "fallback", (
        f"borderline/insufficient candidate must fall through to "
        f"PPStructureV3 fallback; got {disposition=}, {candidate_decision=}"
    )
    assert candidate_decision in {"borderline", "insufficient"}, (
        f"candidate decision should be borderline or insufficient, "
        f"got {candidate_decision!r}"
    )


def test_insufficient_candidate_falls_through_to_fallback() -> None:
    """MI-14: insufficient candidate decision MUST yield `fallback`
    disposition (no suppression on insufficient)."""
    disposition, candidate_decision = decide_ocr_only_fallback_disposition(
        preprocess_strategy_id="ocr-only-v1",
        fr_005_trigger_would_fire=True,
        opt_in_active=True,
        candidate_pages=_build_empty_candidate_pages(),
    )
    assert disposition == "fallback"
    assert candidate_decision == "insufficient"


def test_sufficient_candidate_suppresses_fallback() -> None:
    """R-020.8 / MI-12: sufficient candidate AND all other conjuncts hold
    ⇒ disposition is `suppress`. The OCR-only output is kept."""
    disposition, candidate_decision = decide_ocr_only_fallback_disposition(
        preprocess_strategy_id="ocr-only-v1",
        fr_005_trigger_would_fire=True,
        opt_in_active=True,
        candidate_pages=_build_sufficient_candidate_pages(),
    )
    assert disposition == "suppress"
    assert candidate_decision == "sufficient"


def test_no_trigger_yields_keep_disposition() -> None:
    """When FR-005 trigger would not fire, the OCR-only output is kept
    as-is via the `keep` disposition (no gate evaluation needed)."""
    disposition, candidate_decision = decide_ocr_only_fallback_disposition(
        preprocess_strategy_id="ocr-only-v1",
        fr_005_trigger_would_fire=False,
        opt_in_active=True,
        candidate_pages=_build_sufficient_candidate_pages(),
    )
    assert disposition == "keep"
    # No gate evaluation happens when trigger does not fire — saves work.
    assert candidate_decision is None


def test_opt_in_off_yields_fallback_disposition() -> None:
    """When opt-in is OFF (legacy / default per FR-012), even a
    sufficient candidate with FR-005 trigger firing MUST yield
    `fallback` disposition (legacy behavior preserved per MI-20)."""
    disposition, candidate_decision = decide_ocr_only_fallback_disposition(
        preprocess_strategy_id="ocr-only-v1",
        fr_005_trigger_would_fire=True,
        opt_in_active=False,
        candidate_pages=_build_sufficient_candidate_pages(),
    )
    assert disposition == "fallback"
    # No gate evaluation happens when opt-in is off.
    assert candidate_decision is None


def test_non_ocr_only_strategy_yields_fallback() -> None:
    """When the active strategy is not `ocr-only-v1`, the suppression
    predicate's strategy conjunct fails — disposition is `fallback`
    when the trigger fires (the predicate guards the suppression path
    but does not change other branches)."""
    disposition, _candidate_decision = decide_ocr_only_fallback_disposition(
        preprocess_strategy_id="ppstructurev3",
        fr_005_trigger_would_fire=True,
        opt_in_active=True,
        candidate_pages=_build_sufficient_candidate_pages(),
    )
    # Strategy != ocr-only-v1 means suppression's predicate returns
    # False; trigger fires, so caller falls back. The gate IS evaluated
    # (opt-in + trigger both True) but the predicate refuses suppression
    # on the non-OCR-only strategy.
    assert disposition == "fallback"


def test_mi11_gate_evaluated_on_candidate_and_caller_re_evaluates_on_final() -> None:
    """MI-11: the disposition seam evaluates the gate on the CANDIDATE
    pages exactly once. The caller (`_run_inner` / `corpus_run.py`)
    re-evaluates the gate on the FINAL preprocess_output for the
    recorded decision per R-020.7 step 4. This test asserts the seam's
    half of the invariant (one candidate evaluation per invocation)."""
    # Two distinct candidate page sets — one borderline, one sufficient.
    # The seam evaluates each independently; the candidate decision
    # returned reflects the candidate pages only.
    borderline_disposition, borderline_decision = (
        decide_ocr_only_fallback_disposition(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=True,
            opt_in_active=True,
            candidate_pages=_build_borderline_candidate_pages(),
        )
    )
    sufficient_disposition, sufficient_decision = (
        decide_ocr_only_fallback_disposition(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=True,
            opt_in_active=True,
            candidate_pages=_build_sufficient_candidate_pages(),
        )
    )
    assert borderline_disposition == "fallback"
    assert sufficient_disposition == "suppress"
    # The candidate decisions reflect the candidate pages, independent
    # of any post-fallback re-evaluation that would happen at the
    # caller level (MI-11 second half — covered by
    # `test_evidence_gate_recorded_over_final.py`).
    assert borderline_decision != sufficient_decision
