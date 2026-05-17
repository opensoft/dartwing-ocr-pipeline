"""Feature 020 / T022 / R-020.9 / R-020.10 / FR-008 / FR-010 / FR-011 /
FR-022 / MI-16 / MI-17 / MI-19 / SC-003 / SC-009: run_summary schema bump
0.1.6 → 0.1.7 and the four additive top-level fields.

Asserts:

- ``SCHEMA_VERSION`` is exactly ``"0.1.7"``.
- All four new top-level fields are present on every emitted run_summary
  with the correct default values.
- ``evidence_gate_state_counts`` has all three keys (NOT sparse).
- The four new fields appear AFTER feature 019's two fields.
- **C7 / FR-003 PII-safety closure**: ``evidence_gate_documents`` element
  shape is locked — only ``document_id``, ``decision``, ``signals``; the
  nested ``signals`` object has ONLY the five FR-001 signal names with
  the right types (int / int / float / bool / bool).
- Features 014–019 keys remain byte-identical to the captured pre-020
  baseline fixture (MI-19 / FR-011 / FR-022 / SC-009).
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlinc_ocr.pipeline.timing import RunSummary, SCHEMA_VERSION
from ledgerlinc_ocr.preprocessing.evidence_gate import (
    EvidenceGateResult,
    FiveSignalSet,
    build_evidence_gate_document_record,
)

BASELINE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "feature_020_baseline"
    / "run_summary_pre_020.json"
)


def _minimal_summary() -> RunSummary:
    return RunSummary(
        stack_preset="cpu-default",
        resolved_profiles={},
        execution_slice={},
        on_failure="abort",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )


def test_schema_version_is_0_1_7() -> None:
    """R-020.9 codebase-level bump."""
    assert SCHEMA_VERSION == "0.1.7"
    rs = _minimal_summary()
    assert rs.to_dict()["schema_version"] == "0.1.7"


def test_four_new_fields_present_with_defaults() -> None:
    """Always-emit: all four fields present with defaults on a stub-adapter
    style minimal summary (MI-16 / FR-008 / FR-010)."""
    d = _minimal_summary().to_dict()
    assert d["evidence_gate_id"] == "v1"
    assert d["evidence_gate_state_counts"] == {
        "sufficient": 0,
        "borderline": 0,
        "insufficient": 0,
    }
    assert d["evidence_gate_documents"] == []
    assert d["evidence_gate_suppressed_fallback_count"] == 0


def test_state_counts_object_not_sparse() -> None:
    """MI-17 / R-020.10: ``evidence_gate_state_counts`` MUST have all three
    keys present even when every counter is zero. Sparse object would
    force consumers to handle missing keys — forbidden."""
    d = _minimal_summary().to_dict()
    keys = set(d["evidence_gate_state_counts"].keys())
    assert keys == {"sufficient", "borderline", "insufficient"}


def test_four_new_fields_appear_after_feature_019_fields() -> None:
    """Deterministic order — the four new fields MUST appear AFTER
    feature 019's ``preprocess_strategy_id`` and ``ocr_only_fallback_count``
    (R-020.10 / contracts/run-summary-schema.md §Order of keys)."""
    d = _minimal_summary().to_dict()
    keys = list(d.keys())
    # Locate feature 019's two fields.
    assert "preprocess_strategy_id" in keys
    assert "ocr_only_fallback_count" in keys
    idx_019_last = max(
        keys.index("preprocess_strategy_id"),
        keys.index("ocr_only_fallback_count"),
    )
    # All four new fields must come after the latter feature 019 field.
    for new_field in (
        "evidence_gate_id",
        "evidence_gate_state_counts",
        "evidence_gate_documents",
        "evidence_gate_suppressed_fallback_count",
    ):
        assert keys.index(new_field) > idx_019_last, (
            f"{new_field!r} must come after feature 019's fields"
        )


def test_four_new_fields_in_documented_order() -> None:
    """The four new fields appear in this exact order: id, state_counts,
    documents, suppressed_fallback_count (R-020.10)."""
    d = _minimal_summary().to_dict()
    keys = list(d.keys())
    expected_order = [
        "evidence_gate_id",
        "evidence_gate_state_counts",
        "evidence_gate_documents",
        "evidence_gate_suppressed_fallback_count",
    ]
    indices = [keys.index(name) for name in expected_order]
    assert indices == sorted(indices), (
        f"new fields not in documented order. got positions: "
        f"{dict(zip(expected_order, indices))}"
    )


def test_features_014_to_019_keys_byte_identical_to_baseline() -> None:
    """MI-19 / FR-011 / FR-022 / SC-009: every key emitted on the
    pre-feature-020 baseline (features 014–019) MUST still be emitted
    on a 0.1.7 summary with the SAME type. Schema version is the only
    expected difference; the four new fields are additive (not in
    baseline)."""
    if not BASELINE_FIXTURE.exists():
        # T003 should have produced this fixture before this test ran;
        # if missing, the test is genuinely meaningful (we can't verify
        # carry-forward without a baseline) — fail loudly.
        raise AssertionError(
            f"baseline fixture not captured: {BASELINE_FIXTURE} — "
            f"run T003 first"
        )
    baseline = json.loads(BASELINE_FIXTURE.read_text())
    d = _minimal_summary().to_dict()
    # Every baseline key (except schema_version which we expect to differ)
    # must still be present in the 0.1.7 emission.
    for key in baseline:
        if key == "schema_version":
            continue
        assert key in d, (
            f"feature 020 dropped pre-020 key {key!r} from run_summary — "
            f"FR-011 violation"
        )
        # Type carry-forward (FR-022).
        assert type(d[key]) is type(baseline[key]), (
            f"feature 020 retyped key {key!r}: was "
            f"{type(baseline[key]).__name__}, now {type(d[key]).__name__}"
        )


def test_pii_safety_closure_signals_keys_are_exactly_five(
) -> None:
    """C7 / FR-003 PII-safety closure: ``evidence_gate_documents[i].signals``
    MUST have EXACTLY the five FR-001 signal names — no extras. A future
    regression that adds a raw-text field (e.g., ``vendor_name_candidate_tokens``,
    ``matched_tax_id_values``) MUST fail this assertion."""
    # Build a real EvidenceGateResult and the corresponding record.
    signals = FiveSignalSet(
        vendor_name_candidate_count=3,
        header_band_token_density=14,
        ocr_detection_confidence_mean=0.84,
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    result = EvidenceGateResult(
        signals=signals, decision="sufficient", evidence_gate_id="v1"
    )
    record = build_evidence_gate_document_record(
        document_id="inv_001_easy", result=result
    )
    # Top-level keys of the per-doc record.
    assert set(record.keys()) == {"document_id", "decision", "signals"}, (
        f"per-doc record has unexpected keys: {set(record.keys())} — "
        f"PII closure violation; only document_id/decision/signals allowed"
    )
    # Nested signals object — EXACTLY five keys, no extras.
    expected_signal_keys = {
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }
    assert set(record["signals"].keys()) == expected_signal_keys, (
        f"signals object has unexpected keys: {set(record['signals'].keys())}"
        f" — PII closure violation; raw-text leakage forbidden"
    )
    # Value types are exactly int/int/float/bool/bool.
    assert isinstance(record["signals"]["vendor_name_candidate_count"], int)
    assert isinstance(record["signals"]["header_band_token_density"], int)
    assert isinstance(record["signals"]["ocr_detection_confidence_mean"], float)
    assert isinstance(record["signals"]["business_suffix_present"], bool)
    assert isinstance(record["signals"]["tax_id_shaped_present"], bool)


def test_pii_safety_closure_via_real_doc_emission() -> None:
    """Same closure but exercised through ``RunSummary.to_dict()`` to catch
    leakage at the serializer boundary."""
    signals = FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=8,
        ocr_detection_confidence_mean=0.70,
        business_suffix_present=True,
        tax_id_shaped_present=False,
    )
    result = EvidenceGateResult(
        signals=signals, decision="sufficient", evidence_gate_id="v1"
    )
    record = build_evidence_gate_document_record(
        document_id="inv_001_easy", result=result
    )
    rs = _minimal_summary()
    rs.evidence_gate_documents.append(record)
    d = rs.to_dict()
    assert len(d["evidence_gate_documents"]) == 1
    emitted = d["evidence_gate_documents"][0]
    assert set(emitted.keys()) == {"document_id", "decision", "signals"}
    assert set(emitted["signals"].keys()) == {
        "vendor_name_candidate_count",
        "header_band_token_density",
        "ocr_detection_confidence_mean",
        "business_suffix_present",
        "tax_id_shaped_present",
    }


def test_state_counts_dict_can_be_mutated_safely_per_instance() -> None:
    """``default_factory`` produces a FRESH dict per RunSummary — two
    instances do not share a mutable default."""
    a = _minimal_summary()
    b = _minimal_summary()
    a.evidence_gate_state_counts["sufficient"] = 5
    assert b.evidence_gate_state_counts["sufficient"] == 0


def test_state_counts_emitted_as_exact_three_keys_even_if_internal_sparse(
) -> None:
    """Defense in depth at the serializer boundary: even if a caller
    accidentally builds a sparse state_counts dict, ``to_dict()`` MUST
    emit all three keys with the missing ones at zero (MI-17 defense
    in depth)."""
    rs = _minimal_summary()
    # Corrupt the dict to sparse form intentionally.
    rs.evidence_gate_state_counts.clear()
    rs.evidence_gate_state_counts["sufficient"] = 3
    d = rs.to_dict()
    assert d["evidence_gate_state_counts"] == {
        "sufficient": 3,
        "borderline": 0,
        "insufficient": 0,
    }
