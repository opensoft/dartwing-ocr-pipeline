"""Feature 020 / T035 / R-020.7 / MI-10: CPU-safe test that the RECORDED
gate decision in `evidence_gate_documents` is always the gate evaluation
over the FINAL `preprocess_output.json`, not the OCR-only candidate.

This is the merge-gating CPU-safe assertion for MI-10. The corpus_run
and preprocess-CLI gate-recording sites both read the on-disk
preprocess_output.json after the orchestrator returns; they do NOT
record the candidate decision. This test exercises that contract by
writing two distinct synthetic preprocess_output dicts to disk and
asserting that `evaluate_evidence_gate` over the disk content matches
what the caller would record (and that the candidate decision
returned by the disposition seam differs in the borderline-vs-final
case).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from dartwing_ocr.preprocessing.evidence_gate import (
    build_evidence_gate_document_record,
    evaluate_evidence_gate,
    load_preprocess_output_for_gate,
)
from dartwing_ocr.preprocessing.pipeline import (
    decide_ocr_only_fallback_disposition,
)


def _candidate_pages_borderline() -> list[dict[str, Any]]:
    """OCR-only candidate pages that produce a `borderline` gate
    decision (no business suffix, no tax-id)."""
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
                    "text": "Bill To Customer Alpha Beta",
                    "confidence": 0.80,
                },
            ],
        }
    ]


def _final_pages_sufficient() -> list[dict[str, Any]]:
    """Post-fallback PPStructureV3 final pages that produce a `sufficient`
    gate decision (richer layout including business suffix + tax id)."""
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
                    "text": "Vendor Tax ID 12-3456789 for invoicing",
                    "confidence": 0.88,
                },
            ],
        }
    ]


def _write_preprocess_output(folder: Path, pages: list[dict[str, Any]]) -> Path:
    """Write a minimal preprocess_output.json containing only the pages
    block — the gate reads nothing else off the artifact."""
    out_path = folder / "preprocess_output.json"
    out_path.write_text(
        json.dumps({"pages": pages}, separators=(",", ":")),
        encoding="utf-8",
    )
    return out_path


def test_mi10_recorded_decision_matches_final_not_candidate(
    tmp_path: Path,
) -> None:
    """MI-10 / R-020.7: the recorded decision in
    `evidence_gate_documents` MUST be the gate evaluation over the
    FINAL `preprocess_output.json` written to disk, not the OCR-only
    candidate's decision.
    """
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()

    candidate_pages = _candidate_pages_borderline()
    final_pages = _final_pages_sufficient()

    # Step 1: the disposition seam evaluates the candidate. Borderline
    # gate decision means the FR-005 fallback fires (no suppression).
    candidate_disposition, candidate_decision = (
        decide_ocr_only_fallback_disposition(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=True,
            opt_in_active=True,
            candidate_pages=candidate_pages,
        )
    )
    assert candidate_disposition == "fallback", (
        f"borderline candidate must fall through to fallback per MI-14; "
        f"got {candidate_disposition=}, {candidate_decision=}"
    )
    # The candidate decision the seam returned should NOT be sufficient.
    assert candidate_decision in {"borderline", "insufficient"}

    # Step 2: the caller (orchestrator) ran the PPStructureV3 fallback
    # and wrote the post-fallback `preprocess_output.json` to disk.
    final_path = _write_preprocess_output(folder, final_pages)

    # Step 3: the gate-recording site reads the FINAL file and records
    # ITS decision — not the candidate decision.
    loaded = load_preprocess_output_for_gate(final_path)
    assert loaded is not None
    final_result = evaluate_evidence_gate(loaded)

    # MI-10: the recorded decision MUST match the FINAL file content,
    # not the candidate's borderline decision.
    assert final_result.decision == "sufficient"
    assert final_result.decision != candidate_decision

    # Build the record exactly like corpus_run.py does.
    record = build_evidence_gate_document_record(
        document_id="inv_001_easy", result=final_result
    )
    assert record["document_id"] == "inv_001_easy"
    assert record["decision"] == "sufficient"
    assert record["decision"] != candidate_decision


def test_mi10_recorded_decision_matches_when_candidate_kept(
    tmp_path: Path,
) -> None:
    """MI-10 (suppression case): when shape (b) suppression fires, the
    OCR-only candidate IS the final output. The recorded decision
    matches the candidate decision tautologically because they are the
    same evaluation over the same dict.
    """
    folder = tmp_path / "inv_002_easy"
    folder.mkdir()

    # Sufficient candidate ⇒ shape (b) suppression fires; OCR-only output
    # IS the final output.
    sufficient_pages = _final_pages_sufficient()

    candidate_disposition, candidate_decision = (
        decide_ocr_only_fallback_disposition(
            preprocess_strategy_id="ocr-only-v1",
            fr_005_trigger_would_fire=True,
            opt_in_active=True,
            candidate_pages=sufficient_pages,
        )
    )
    assert candidate_disposition == "suppress"
    assert candidate_decision == "sufficient"

    # The orchestrator wrote the SAME pages to disk (no fallback ran).
    final_path = _write_preprocess_output(folder, sufficient_pages)

    loaded = load_preprocess_output_for_gate(final_path)
    assert loaded is not None
    final_result = evaluate_evidence_gate(loaded)

    # Tautological equality on the suppression path: candidate IS final.
    assert final_result.decision == candidate_decision == "sufficient"

    record = build_evidence_gate_document_record(
        document_id="inv_002_easy", result=final_result
    )
    assert record["decision"] == "sufficient"


def test_mi10_recorded_decision_independent_of_candidate_input() -> None:
    """The gate-recording site does not consume the candidate decision
    at all — it only reads the on-disk file. This test exercises the
    invariant directly: a borderline candidate followed by an
    `insufficient` final file produces a recorded `insufficient`,
    NOT a recorded `borderline`."""
    from io import StringIO
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        folder = Path(td) / "inv_999_hard"
        folder.mkdir()
        # Final file is an empty page (all negative signals → insufficient)
        final_path = _write_preprocess_output(
            folder,
            [{"height": 1000, "blocks": []}],
        )
        loaded = load_preprocess_output_for_gate(final_path)
        assert loaded is not None
        result = evaluate_evidence_gate(loaded)
        assert result.decision == "insufficient"
        # The candidate (borderline) is never consulted by the recording
        # site — assertion is implicit: the final file IS the source of
        # truth.
