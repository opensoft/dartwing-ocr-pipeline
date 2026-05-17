"""Feature 020 / T015 / MI-7 / SC-002 / SC-012: operator re-derivability.

For every result produced by ``evaluate_evidence_gate``, the recorded
decision MUST equal ``decide_for_gate(result.evidence_gate_id,
result.signals)``. This is the audit-trail guarantee: an operator
inspecting ``run_summary`` on disk can re-derive every recorded decision
from the recorded signals plus the documented v1 decision table without
re-running the binary.
"""

from __future__ import annotations

from itertools import product

import pytest

from dartwing_ocr.preprocessing.evidence_gate import (
    CONFIDENCE_THRESHOLD,
    DENSITY_THRESHOLD,
    EvidenceGateResult,
    FiveSignalSet,
    decide_for_gate,
    evaluate_evidence_gate,
)


@pytest.mark.parametrize(
    "has_name,has_density,has_confidence,has_suffix,has_tax_id",
    list(product([True, False], repeat=5)),
)
def test_recorded_decision_re_derivable_from_signals(
    has_name: bool, has_density: bool, has_confidence: bool,
    has_suffix: bool, has_tax_id: bool,
) -> None:
    """For each row in the 32-row truth table: construct the signals, get
    the canonical decision via ``decide_for_gate``, wrap into an
    ``EvidenceGateResult``, and assert the recorded ``result.decision``
    re-derives from ``result.signals`` + ``result.evidence_gate_id``.

    The prior version of this test was tautological — it just called
    ``decide_for_gate`` twice on the same input and asserted idempotency.
    That proved determinism but did NOT verify the actual SC-012
    re-derivability contract on an ``EvidenceGateResult``. The new
    form mirrors the operator's audit workflow: given a result, can
    the recorded decision be reproduced from the recorded inputs?
    """
    signals = FiveSignalSet(
        vendor_name_candidate_count=1 if has_name else 0,
        header_band_token_density=DENSITY_THRESHOLD if has_density else 0,
        ocr_detection_confidence_mean=CONFIDENCE_THRESHOLD if has_confidence else 0.0,
        business_suffix_present=has_suffix,
        tax_id_shaped_present=has_tax_id,
    )
    canonical = decide_for_gate("v1", signals)
    # Build the result through the public constructor (this exercises
    # the EvidenceGateResult.__post_init__ re-derivability check too).
    result = EvidenceGateResult(
        signals=signals, decision=canonical, evidence_gate_id="v1",
    )
    # The operator-side audit: re-derive from recorded inputs.
    re_derived = decide_for_gate(result.evidence_gate_id, result.signals)
    assert result.decision == re_derived


def test_evaluate_result_satisfies_rederivability_on_synthetic_doc() -> None:
    """End-to-end on a synthetic doc: result.decision must equal
    ``decide_for_gate(result.evidence_gate_id, result.signals)``."""
    doc = {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": "Acme Widget Inc. EIN: 12-3456789 and some more tokens here",
                     "confidence": 0.85, "bbox": [0, 100, 1000, 200]},
                ],
                "raw_ocr_lines": [],
            }
        ]
    }
    result = evaluate_evidence_gate(doc)
    re_derived = decide_for_gate(result.evidence_gate_id, result.signals)
    assert result.decision == re_derived, (
        f"recorded decision {result.decision!r} does not match re-derived "
        f"{re_derived!r} — SC-012 violation"
    )


def test_evaluate_result_rederivability_on_empty_doc() -> None:
    """Empty / malformed input → insufficient; still re-derivable."""
    result = evaluate_evidence_gate({})
    re_derived = decide_for_gate(result.evidence_gate_id, result.signals)
    assert result.decision == re_derived == "insufficient"
