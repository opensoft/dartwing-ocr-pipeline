"""US4 T054: quality_status truth-table coverage (R-023.20).

Parameterized across the 6 rows of the (gate state × manual_review_required)
table. Each row asserts (quality_status, quality_status_source) directly via
the ``derive_quality_status`` function — no full pipeline run required.
"""

from __future__ import annotations

import pytest

from dartwing_ocr.gpu_demo.quality_status import (
    EvaluatorVerdict,
    derive_quality_status,
)


@pytest.mark.parametrize(
    "gate_state, manual_review, expected_status",
    [
        ("sufficient", False, "pass"),
        ("sufficient", True, "review_required"),
        ("borderline", False, "weak"),
        ("borderline", True, "review_required"),
        ("insufficient", False, "review_required"),
        ("insufficient", True, "review_required"),
    ],
)
def test_truth_table_gate_only(gate_state, manual_review, expected_status):
    status, source = derive_quality_status(gate_state, manual_review)
    assert status == expected_status
    assert source == "gate"


def test_evaluator_passes_keeps_base_status_flips_source():
    """Evaluator agrees → source flips to 'evaluator', value unchanged."""
    status, source = derive_quality_status(
        "sufficient", False, EvaluatorVerdict(semantic_table_quality_passed=True)
    )
    assert (status, source) == ("pass", "evaluator")


def test_evaluator_fails_downgrades_pass_to_weak():
    """Evaluator says fail + gate says pass → downgrade to weak with source=evaluator."""
    status, source = derive_quality_status(
        "sufficient", False, EvaluatorVerdict(semantic_table_quality_passed=False)
    )
    assert (status, source) == ("weak", "evaluator")


def test_evaluator_fails_cannot_upgrade():
    """Evaluator says fail on already-weak → stays weak (no upgrade)."""
    status, source = derive_quality_status(
        "borderline", False, EvaluatorVerdict(semantic_table_quality_passed=False)
    )
    assert (status, source) == ("weak", "evaluator")


def test_evaluator_fails_review_required_stays_review_required():
    """Evaluator says fail on review_required → stays review_required (no upgrade)."""
    status, source = derive_quality_status(
        "sufficient", True, EvaluatorVerdict(semantic_table_quality_passed=False)
    )
    assert (status, source) == ("review_required", "evaluator")
