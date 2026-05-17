"""Feature 020 / T008a / FR-002: strategy-uniformity test.

Loads captured ``preprocess_output.json`` fixtures (from the existing
``tests/fixtures/extract/`` snapshots produced by prior features) and
asserts ``evaluate_evidence_gate(...)`` succeeds on each, returns the
correct ``FiveSignalSet`` types, and produces a decision in the closed
three-state vocabulary.

The signal VALUES will differ across fixtures (different content) — that
is expected and not asserted. This test verifies the SHAPE / type
uniformity required by FR-002: "MUST be computable on the output of any
preprocessing strategy in scope today" / "MUST NOT require layout-derived
blocks" / "MUST NOT require any feature-018 region-strategy-specific
shape".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    FiveSignalSet,
    evaluate_evidence_gate,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "extract"

# Each fixture is a real preprocess_output.json captured from a different
# extract test scenario in the prior-features test suite. They represent
# what the various preprocessing strategies have actually produced.
FIXTURE_NAMES = (
    "us1_happy",
    "us2_evidence",
    "us3_grounded_name",
    "us3_missing_name",
    "us4_qwen_sim",
    "us5_partial_input",
)


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_gate_runs_on_fixture(fixture_name: str) -> None:
    """For each captured fixture, ``evaluate_evidence_gate`` must succeed
    and return a structurally valid result regardless of which producer
    shape (full-page / header-first-v1 / ppstructurev3 / ocr-only-v1) the
    fixture happens to mirror (FR-002)."""
    fixture_path = FIXTURES_ROOT / fixture_name / "preprocess_output.json"
    if not fixture_path.exists():
        pytest.skip(f"fixture missing: {fixture_path}")
    with open(fixture_path, encoding="utf-8") as f:
        preprocess_output = json.load(f)
    result = evaluate_evidence_gate(preprocess_output)
    # Type uniformity assertions (FR-002 SHAPE clause).
    assert isinstance(result.signals, FiveSignalSet)
    assert isinstance(result.signals.vendor_name_candidate_count, int)
    assert isinstance(result.signals.header_band_token_density, int)
    assert isinstance(result.signals.ocr_detection_confidence_mean, float)
    assert isinstance(result.signals.business_suffix_present, bool)
    assert isinstance(result.signals.tax_id_shaped_present, bool)
    # Decision is in the closed three-state vocabulary.
    assert result.decision in {"sufficient", "borderline", "insufficient"}
    assert result.evidence_gate_id == "v1"
    # Non-negativity invariants.
    assert result.signals.vendor_name_candidate_count >= 0
    assert result.signals.header_band_token_density >= 0
    assert 0.0 <= result.signals.ocr_detection_confidence_mean <= 1.0


def test_gate_runs_on_minimal_layout_free_dict() -> None:
    """OCR-only outputs have ``blocks`` populated but may have empty
    ``raw_ocr_lines``. FR-002: the gate must accept this shape."""
    minimal = {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": "Acme Inc.", "confidence": 0.9, "bbox": [0, 100, 100, 200]}
                ],
                "raw_ocr_lines": [],
            }
        ]
    }
    result = evaluate_evidence_gate(minimal)
    assert result.evidence_gate_id == "v1"
    assert result.decision in {"sufficient", "borderline", "insufficient"}
