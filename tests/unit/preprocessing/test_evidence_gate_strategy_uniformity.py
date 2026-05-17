"""Feature 020 / T008a / FR-002: strategy-uniformity test.

The gate is a pure read over ``preprocess_output.json`` and MUST be
computable on the output of any preprocessing strategy in scope today —
``ppstructurev3``, ``ocr-only-v1``, ``header-first-v1``, and a minimal
layout-free shape that older / experimental adapters may produce.

This file uses **synthesized in-memory fixtures** (one per strategy shape)
rather than disk fixtures so CI cannot silently cover zero cases when
the disk-fixture tree is absent (M2 review cleanup — the prior version
used ``pytest.skip(f"fixture missing")`` which collapsed to "tests
passed; 0 fixtures exercised" under that condition).
"""

from __future__ import annotations

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    FiveSignalSet,
    evaluate_evidence_gate,
)

# Each fixture mirrors the structural shape one preprocessing strategy
# produces. Signal values vary by content — that is expected and not
# asserted (FR-002 is about SHAPE uniformity, not value equality).
_PPSTRUCTUREV3_FIXTURE = {
    "pages": [
        {
            "page_number": 1, "width": 2480, "height": 3508,
            "rotation_detected": 0,
            "blocks": [
                {"text": "Acme Widget Inc.", "confidence": 0.92,
                 "bbox": [120, 180, 720, 240], "type": "title"},
                {"text": "INVOICE #4567", "confidence": 0.88,
                 "bbox": [1800, 200, 2300, 260], "type": "title"},
                {"text": "Bill To: Customer LLC", "confidence": 0.85,
                 "bbox": [120, 320, 900, 380], "type": "paragraph"},
                {"text": "EIN: 12-3456789", "confidence": 0.91,
                 "bbox": [120, 450, 700, 510], "type": "paragraph"},
            ],
            "tables": [],
            "raw_ocr_lines": [],
        }
    ]
}

_OCR_ONLY_V1_FIXTURE = {
    "pages": [
        {
            "page_number": 1, "width": 2480, "height": 3508,
            "rotation_detected": 0,
            "blocks": [
                {"text": "Northwind Trading Ltd", "confidence": 0.78,
                 "bbox": [100, 150, 800, 210]},
                {"text": "VAT: GB123456789", "confidence": 0.81,
                 "bbox": [100, 250, 700, 310]},
            ],
            "raw_ocr_lines": [
                {"text": "Northwind Trading Ltd", "confidence": 0.78,
                 "bbox": [100, 150, 800, 210]},
            ],
        }
    ]
}

_HEADER_FIRST_V1_FIXTURE = {
    "pages": [
        {
            "page_number": 1, "width": 2480, "height": 3508,
            "rotation_detected": 0,
            "blocks": [
                {"text": "Globex Corporation", "confidence": 0.83,
                 "bbox": [200, 100, 900, 170]},
                {"text": "tax id 98-7654321", "confidence": 0.79,
                 "bbox": [200, 200, 700, 260]},
            ],
            "raw_ocr_lines": [],
        }
    ]
}

_MINIMAL_LAYOUT_FREE_FIXTURE = {
    "pages": [
        {
            "page_number": 1, "width": 1000, "height": 1000,
            "rotation_detected": 0,
            "blocks": [
                {"text": "Acme Inc.", "confidence": 0.9,
                 "bbox": [0, 100, 100, 200]},
            ],
            "raw_ocr_lines": [],
        }
    ]
}

_FIXTURES = {
    "ppstructurev3": _PPSTRUCTUREV3_FIXTURE,
    "ocr-only-v1": _OCR_ONLY_V1_FIXTURE,
    "header-first-v1": _HEADER_FIRST_V1_FIXTURE,
    "minimal-layout-free": _MINIMAL_LAYOUT_FREE_FIXTURE,
}


@pytest.mark.parametrize("strategy_name", sorted(_FIXTURES))
def test_gate_runs_on_strategy_shape(strategy_name: str) -> None:
    """For each preprocessing-strategy shape, ``evaluate_evidence_gate``
    must succeed and return a structurally valid result (FR-002 SHAPE
    uniformity)."""
    preprocess_output = _FIXTURES[strategy_name]
    result = evaluate_evidence_gate(preprocess_output)
    assert isinstance(result.signals, FiveSignalSet)
    assert isinstance(result.signals.vendor_name_candidate_count, int)
    assert isinstance(result.signals.header_band_token_density, int)
    assert isinstance(result.signals.ocr_detection_confidence_mean, float)
    assert isinstance(result.signals.business_suffix_present, bool)
    assert isinstance(result.signals.tax_id_shaped_present, bool)
    assert result.decision in {"sufficient", "borderline", "insufficient"}
    assert result.evidence_gate_id == "v1"
    assert result.signals.vendor_name_candidate_count >= 0
    assert result.signals.header_band_token_density >= 0
    assert 0.0 <= result.signals.ocr_detection_confidence_mean <= 1.0


def test_all_strategy_shapes_actually_exercised() -> None:
    """Defense against accidental fixture-set shrinkage — the parametrize
    must cover all four shapes."""
    assert set(_FIXTURES.keys()) == {
        "ppstructurev3", "ocr-only-v1", "header-first-v1",
        "minimal-layout-free",
    }
