"""quality_status derivation truth-table (T017, R-023.20).

Two inputs: the evidence-gate state (feature 020) + the
``manual_review_required`` flag from the final structured payload (feature 009).
An optional evaluator verdict (feature 022) may *downgrade* the result but
never *upgrade* it — preserving the safety property that manual review is
never silently skipped (R-023.20).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from dartwing_ocr.gpu_demo.enums import QualityStatus, QualityStatusSource


@dataclass(frozen=True)
class EvaluatorVerdict:
    """Subset of feature 022 evaluator output the demo consumes.

    The demo treats ``semantic_table_quality_passed = False`` as a downgrade
    signal; True means "evaluator agrees with the gate-derived verdict".
    """

    semantic_table_quality_passed: bool


# Truth-table per R-023.20 (gate state × manual_review_required → quality_status).
_GATE_TRUTH_TABLE: dict[tuple[str, bool], QualityStatus] = {
    ("sufficient", False): "pass",
    ("sufficient", True): "review_required",
    ("borderline", False): "weak",
    ("borderline", True): "review_required",
    ("insufficient", False): "review_required",
    ("insufficient", True): "review_required",
}


def derive_quality_status(
    gate_state: str,
    manual_review_required: bool,
    evaluator_result: Optional[EvaluatorVerdict] = None,
) -> tuple[QualityStatus, QualityStatusSource]:
    """Compute the demo's ``(quality_status, quality_status_source)`` pair.

    On unknown ``gate_state`` (defensive — feature 020 should always emit one of
    the three closed values), defaults to ``review_required`` to preserve safety.
    """
    base: QualityStatus = _GATE_TRUTH_TABLE.get(
        (gate_state, manual_review_required), "review_required"
    )

    if evaluator_result is None:
        return base, "gate"

    # Evaluator can downgrade but not upgrade. Downgrade rule:
    # - If evaluator says fail → never report "pass". Demote to "weak".
    # - If evaluator says fail and gate-derived is already "weak" or
    #   "review_required" → no change in value, but source flips to "evaluator".
    if not evaluator_result.semantic_table_quality_passed:
        if base == "pass":
            return "weak", "evaluator"
        return base, "evaluator"

    # Evaluator agrees — source flips to "evaluator", base preserved.
    return base, "evaluator"
