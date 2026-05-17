"""Feature 020 / T016 / R-020.2 / MI-25 / MI-26: closed-vocabulary
preset-registry tests.

Asserts:

- ``EVIDENCE_GATES`` contains exactly one entry at landing: ``"v1"`` (MI-25).
- ``EvidenceGate.decide`` returns only the three closed-vocabulary literals
  ``"sufficient"`` / ``"borderline"`` / ``"insufficient"`` (MI-26).
- Module-level constants ``EVIDENCE_GATE_ID_V1`` and
  ``EVIDENCE_GATE_ID_DEFAULT`` are wired to the registry's only entry.
- Re-importing the module produces the same registry contents
  (deterministic at module load).
"""

from __future__ import annotations

import importlib

import pytest

from ledgerlinc_ocr.preprocessing.evidence_gate import (
    CONFIDENCE_THRESHOLD,
    DENSITY_THRESHOLD,
    EVIDENCE_GATES,
    EvidenceGate,
    FiveSignalSet,
    Y_THRESHOLD_FRACTION,
)
from ledgerlinc_ocr.preprocessing.identifiers import (
    EVIDENCE_GATE_ID_DEFAULT,
    EVIDENCE_GATE_ID_V1,
)


def test_registry_size_at_landing_is_one() -> None:
    """At landing, the closed-vocabulary registry has exactly one entry."""
    assert len(EVIDENCE_GATES) == 1


def test_registry_only_key_is_v1() -> None:
    """The only valid `evidence_gate_id` at landing is `"v1"`."""
    assert set(EVIDENCE_GATES.keys()) == {"v1"}


def test_v1_preset_is_evidence_gate_instance() -> None:
    """Registry value is an ``EvidenceGate`` (frozen) instance."""
    preset = EVIDENCE_GATES["v1"]
    assert isinstance(preset, EvidenceGate)


def test_v1_preset_id_matches_constant() -> None:
    """``EVIDENCE_GATES['v1'].evidence_gate_id == "v1"`` consistency."""
    assert EVIDENCE_GATES["v1"].evidence_gate_id == EVIDENCE_GATE_ID_V1
    assert EVIDENCE_GATE_ID_V1 == "v1"
    assert EVIDENCE_GATE_ID_DEFAULT == EVIDENCE_GATE_ID_V1


def test_v1_preset_thresholds_pinned() -> None:
    """Module-level constants match the v1 preset's thresholds (R-020.5 / R-020.6)."""
    preset = EVIDENCE_GATES["v1"]
    assert preset.y_threshold_fraction == Y_THRESHOLD_FRACTION == 0.25
    assert preset.density_threshold == DENSITY_THRESHOLD == 8
    assert preset.confidence_threshold == CONFIDENCE_THRESHOLD == 0.70


def test_decide_returns_closed_vocabulary(
) -> None:
    """``EvidenceGate.decide`` returns only the three closed-vocabulary
    literals (MI-26). Exhaustive across the 32-row truth table."""
    from itertools import product
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
        decision = EVIDENCE_GATES["v1"].decide(signals)
        assert decision in closed_vocab, (
            f"v1 decide returned non-vocabulary value {decision!r} "
            f"on {signals!r}"
        )


def test_registry_is_immutable_evidence_gate_instances_frozen() -> None:
    """The ``EvidenceGate`` dataclass is frozen — mutating its fields raises
    ``FrozenInstanceError`` (MI-8 / data-model.md §1)."""
    from dataclasses import FrozenInstanceError
    preset = EVIDENCE_GATES["v1"]
    with pytest.raises(FrozenInstanceError):
        preset.y_threshold_fraction = 0.5  # type: ignore[misc]


def test_module_reload_produces_same_registry() -> None:
    """Re-importing ``evidence_gate`` produces the same registry shape
    (deterministic at module load — no random state, no env-var
    influence on registry construction)."""
    module = importlib.import_module("ledgerlinc_ocr.preprocessing.evidence_gate")
    reloaded = importlib.reload(module)
    assert set(reloaded.EVIDENCE_GATES.keys()) == {"v1"}
    assert reloaded.EVIDENCE_GATES["v1"].evidence_gate_id == "v1"
    assert reloaded.EVIDENCE_GATES["v1"].y_threshold_fraction == 0.25
