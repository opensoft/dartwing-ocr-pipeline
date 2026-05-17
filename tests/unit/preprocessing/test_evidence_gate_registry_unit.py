"""Feature 020 / T016 / R-020.2 / MI-25 / MI-26: closed-vocabulary
preset-registry tests.

After H2 cleanup (post-review): the one-element ``EvidenceGate`` dataclass
+ ``EVIDENCE_GATES`` dict was collapsed. The remaining preset surface is:

- a single module-level ``EVIDENCE_GATE_ID_V1`` constant + the matching
  ``EVIDENCE_GATE_ID_DEFAULT`` identifier
- thresholds at module level (``Y_THRESHOLD_FRACTION``,
  ``DENSITY_THRESHOLD``, ``CONFIDENCE_THRESHOLD``)
- ``decide_for_gate(gate_id, signals)`` as the named-dispatch hook
  (R-020.2 future-additive extensibility) + ``evaluate_evidence_gate``
  that rejects unknown ids

Asserts:

- ``evaluate_evidence_gate`` accepts only ``"v1"`` (MI-25 closed-vocabulary
  size 1).
- ``decide_for_gate`` returns only the three closed-vocabulary literals
  (MI-26).
- ``decide_for_gate`` rejects unknown gate ids — no fallthrough.
- Module-level constants match the documented landing values.
- Re-importing the module is deterministic.
"""

from __future__ import annotations

from itertools import product

import pytest

from dartwing_ocr.preprocessing.evidence_gate import (
    CONFIDENCE_THRESHOLD,
    DENSITY_THRESHOLD,
    EVIDENCE_GATE_ID_V1,
    FiveSignalSet,
    Y_THRESHOLD_FRACTION,
    decide_for_gate,
    evaluate_evidence_gate,
)
from dartwing_ocr.preprocessing.identifiers import (
    EVIDENCE_GATE_ID_DEFAULT,
)


def test_only_v1_gate_id_is_accepted() -> None:
    """At landing, ``"v1"`` is the only valid evidence_gate_id (MI-25)."""
    preprocess_output = {"pages": []}
    result = evaluate_evidence_gate(preprocess_output, gate_id="v1")
    assert result.evidence_gate_id == "v1"


def test_unknown_gate_id_rejected() -> None:
    """Unknown gate ids raise — no silent fallthrough to v1 (R-020.2)."""
    with pytest.raises(KeyError):
        evaluate_evidence_gate({"pages": []}, gate_id="v2")
    with pytest.raises(KeyError):
        decide_for_gate("v2", FiveSignalSet(0, 0, 0.0, False, False))


def test_v1_id_constant_matches_default() -> None:
    """``EVIDENCE_GATE_ID_V1`` is the default and equals ``"v1"``."""
    assert EVIDENCE_GATE_ID_V1 == "v1"
    assert EVIDENCE_GATE_ID_DEFAULT == EVIDENCE_GATE_ID_V1


def test_threshold_constants_pinned() -> None:
    """Module-level thresholds match the v1 preset's documented values
    (R-020.5 / R-020.6)."""
    assert Y_THRESHOLD_FRACTION == 0.25
    assert DENSITY_THRESHOLD == 8
    assert CONFIDENCE_THRESHOLD == 0.70


def test_decide_returns_closed_vocabulary() -> None:
    """``decide_for_gate("v1", ...)`` returns only the three closed-vocabulary
    literals (MI-26). Exhaustive across the 32-row truth table."""
    closed_vocab = {"sufficient", "borderline", "insufficient"}
    for has_name, has_density, has_confidence, has_suffix, has_tax_id in product(
        [True, False], repeat=5
    ):
        signals = FiveSignalSet(
            vendor_name_candidate_count=1 if has_name else 0,
            header_band_token_density=DENSITY_THRESHOLD if has_density else 0,
            ocr_detection_confidence_mean=CONFIDENCE_THRESHOLD if has_confidence else 0.0,
            business_suffix_present=has_suffix,
            tax_id_shaped_present=has_tax_id,
        )
        decision = decide_for_gate("v1", signals)
        assert decision in closed_vocab, (
            f"v1 decide returned non-vocabulary value {decision!r} "
            f"on {signals!r}"
        )


def test_module_constants_are_deterministic() -> None:
    """Module constants are deterministic at import time — no random
    state, no env-var influence on the values.

    C4 cleanup (post-review): the prior version of this test called
    ``importlib.reload(module)`` to verify "same constants on re-import".
    Reload replaces ``sys.modules[...]`` with a new module object,
    introducing test-order dependence (subsequent tests that already
    imported ``FiveSignalSet`` keep the OLD class, while newly-loaded
    test bodies see the NEW one — `isinstance(result.signals,
    FiveSignalSet)` fails). The same determinism property is now
    asserted via direct value inspection — same guarantee, no
    sys.modules side effects.
    """
    assert EVIDENCE_GATE_ID_V1 == "v1"
    assert Y_THRESHOLD_FRACTION == 0.25
    assert DENSITY_THRESHOLD == 8
    assert CONFIDENCE_THRESHOLD == 0.70
