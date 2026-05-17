"""Feature 020 / T013a / Spec §Edge Cases "Malformed
`preprocess_output.json` reaches the gate": fail-closed behavior.

Asserts that for every malformed-input variant:

- Gate decision is ``"insufficient"`` (all five signals at negative level).
- The gate does NOT raise mid-evaluation.
- Suppression MUST NOT fire on malformed input (will be enforced via
  ``should_suppress_fallback`` in US4; this file exercises the
  ``candidate_gate_decision`` side of the predicate).
"""

from __future__ import annotations

import pytest

from dartwing_ocr.preprocessing.evidence_gate import (
    FiveSignalSet,
    evaluate_evidence_gate,
)


MALFORMED_INPUTS: list[tuple[str, dict]] = [
    ("missing_pages_key", {}),
    ("empty_pages_list", {"pages": []}),
    ("page0_no_blocks_no_geometry", {"pages": [{}]}),
    (
        "page0_explicit_empty_blocks",
        {
            "pages": [
                {
                    "page_number": 1, "width": 1000, "height": 1000,
                    "rotation_detected": 0,
                    "blocks": [],
                    "raw_ocr_lines": [],
                }
            ]
        },
    ),
    (
        "page0_missing_height",
        {
            "pages": [
                {"page_number": 1, "width": 1000, "rotation_detected": 0,
                 "blocks": [{"text": "x", "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
                 "raw_ocr_lines": []}
            ]
        },
    ),
    (
        "page0_zero_height",
        {
            "pages": [
                {"page_number": 1, "width": 1000, "height": 0,
                 "rotation_detected": 0,
                 "blocks": [{"text": "x", "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
                 "raw_ocr_lines": []}
            ]
        },
    ),
    ("pages_wrong_type_string", {"pages": "not a list"}),
    ("pages_wrong_type_int", {"pages": 42}),
    (
        "page0_blocks_wrong_type",
        {
            "pages": [
                {"page_number": 1, "width": 1000, "height": 1000,
                 "rotation_detected": 0,
                 "blocks": None,
                 "raw_ocr_lines": []}
            ]
        },
    ),
]


@pytest.mark.parametrize("name,malformed", MALFORMED_INPUTS)
def test_malformed_input_fails_closed_to_insufficient(
    name: str, malformed: dict
) -> None:
    """Every malformed-input variant → ``insufficient`` decision with all
    five signals at their negative level (spec §Edge Cases)."""
    result = evaluate_evidence_gate(malformed)
    assert result.decision == "insufficient", (
        f"malformed input {name!r} produced {result.decision!r} "
        f"(expected 'insufficient' per spec §Edge Cases)"
    )
    expected_negative = FiveSignalSet(
        vendor_name_candidate_count=0,
        header_band_token_density=0,
        ocr_detection_confidence_mean=0.0,
        business_suffix_present=False,
        tax_id_shaped_present=False,
    )
    assert result.signals == expected_negative, (
        f"malformed input {name!r} produced signals {result.signals!r} "
        f"(expected all five at negative level)"
    )


@pytest.mark.parametrize("name,malformed", MALFORMED_INPUTS)
def test_malformed_input_does_not_raise(name: str, malformed: dict) -> None:
    """``evaluate_evidence_gate`` MUST NOT raise on malformed input — it
    fails closed via the empty-band negative-level tuple. Mid-corpus
    failures degrade gracefully rather than aborting the run."""
    # Just exercise the call path; any exception here is the regression.
    evaluate_evidence_gate(malformed)


def test_unusual_text_field_types_do_not_raise() -> None:
    """Blocks with non-string ``text`` (None, int, list, dict) are silently
    skipped per the gate's defensive iteration — no crash.

    A4 (post-review): blocks whose ``text`` field is non-string used
    to still contribute to the confidence mean; now they are skipped.
    With no contributing blocks, all five signals collapse to negative
    level → decision is ``insufficient``, matching the spec's
    malformed-input edge case (C1 review).
    """
    weird_doc = {
        "pages": [
            {
                "page_number": 1, "width": 1000, "height": 1000,
                "rotation_detected": 0,
                "blocks": [
                    {"text": None, "confidence": 0.9, "bbox": [0, 100, 1, 200]},
                    {"text": 42, "confidence": 0.9, "bbox": [0, 100, 1, 200]},
                    {"text": ["list", "value"], "confidence": 0.9, "bbox": [0, 100, 1, 200]},
                    {"text": {"dict": "value"}, "confidence": 0.9, "bbox": [0, 100, 1, 200]},
                ],
                "raw_ocr_lines": [],
            }
        ]
    }
    result = evaluate_evidence_gate(weird_doc)
    # All blocks contribute 0 tokens AND 0 confidence (A4 filter):
    # density=0, mean=0.0, no name, no suffix, no tax-id → all five
    # at negative level → insufficient.
    assert result.signals.header_band_token_density == 0
    assert result.signals.ocr_detection_confidence_mean == 0.0
    assert result.decision == "insufficient"
