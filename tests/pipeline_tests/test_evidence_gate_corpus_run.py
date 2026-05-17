"""Feature 020 / T023 / R-020.11 / MI-18: aggregate-vs-per-doc consistency
test.

MI-18 invariant: ``evidence_gate_state_counts[s]`` MUST equal the count
of ``evidence_gate_documents[i].decision == s`` for each ``s`` in the
closed three-state vocabulary.

This is a UNIT-level test over synthetic ``RunSummary`` construction —
it does NOT spin up a full stub-adapter corpus run. The full integration
path is exercised by the prior-features pipeline_tests that we did not
break (covered by T060's full CPU regression). The MI-18 invariant
itself is what we want to lock down here.
"""

from __future__ import annotations

from ledgerlinc_ocr.pipeline.timing import RunSummary
from ledgerlinc_ocr.preprocessing.evidence_gate import (
    EvidenceGateResult,
    FiveSignalSet,
    build_evidence_gate_document_record,
)


def _signals_for(decision: str) -> FiveSignalSet:
    """Construct synthetic signals that match the requested decision under
    the v1 decision table. This is convenience for crafting test fixtures
    — the actual ``decision`` we pass to ``EvidenceGateResult`` is the
    truth here; we just need shape-valid signals."""
    if decision == "sufficient":
        return FiveSignalSet(
            vendor_name_candidate_count=3,
            header_band_token_density=14,
            ocr_detection_confidence_mean=0.84,
            business_suffix_present=True,
            tax_id_shaped_present=False,
        )
    if decision == "insufficient":
        return FiveSignalSet(
            vendor_name_candidate_count=0,
            header_band_token_density=0,
            ocr_detection_confidence_mean=0.0,
            business_suffix_present=False,
            tax_id_shaped_present=False,
        )
    return FiveSignalSet(
        vendor_name_candidate_count=1,
        header_band_token_density=4,
        ocr_detection_confidence_mean=0.65,
        business_suffix_present=False,
        tax_id_shaped_present=False,
    )


def _make_record(document_id: str, decision: str) -> dict:
    result = EvidenceGateResult(
        signals=_signals_for(decision),
        decision=decision,
        evidence_gate_id="v1",
    )
    return build_evidence_gate_document_record(
        document_id=document_id, result=result
    )


def test_mi18_aggregate_equals_per_doc_count_synthetic_corpus() -> None:
    """Construct a synthetic 5-document corpus distribution and verify
    state_counts[s] == count(documents | .decision == s) for each s."""
    documents = [
        _make_record("inv_001_easy", "sufficient"),
        _make_record("inv_002_easy", "sufficient"),
        _make_record("inv_006_medium", "borderline"),
        _make_record("inv_011_hard", "insufficient"),
        _make_record("inv_012_hard", "borderline"),
    ]
    state_counts = {"sufficient": 2, "borderline": 2, "insufficient": 1}
    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=5, documents_succeeded=5,
        documents_failed=0,
        evidence_gate_state_counts=state_counts,
        evidence_gate_documents=documents,
    )
    d = rs.to_dict()
    # MI-18: aggregate equals per-doc count for each state.
    for s in ("sufficient", "borderline", "insufficient"):
        expected = sum(1 for r in d["evidence_gate_documents"] if r["decision"] == s)
        assert d["evidence_gate_state_counts"][s] == expected, (
            f"MI-18 violation: state_counts[{s!r}] = "
            f"{d['evidence_gate_state_counts'][s]} but documents has "
            f"{expected} records with that decision"
        )


def test_mi18_empty_corpus_all_zero() -> None:
    """Zero-document run: state_counts all zero, documents empty."""
    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=0, documents_succeeded=0,
        documents_failed=0,
    )
    d = rs.to_dict()
    assert d["evidence_gate_documents"] == []
    assert d["evidence_gate_state_counts"] == {
        "sufficient": 0, "borderline": 0, "insufficient": 0,
    }


def test_mi18_single_decision_class() -> None:
    """Edge case: all documents in the same decision class."""
    documents = [
        _make_record(f"inv_{i:03d}", "sufficient") for i in range(7)
    ]
    state_counts = {"sufficient": 7, "borderline": 0, "insufficient": 0}
    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=7, documents_succeeded=7,
        documents_failed=0,
        evidence_gate_state_counts=state_counts,
        evidence_gate_documents=documents,
    )
    d = rs.to_dict()
    assert d["evidence_gate_state_counts"]["sufficient"] == 7
    assert d["evidence_gate_state_counts"]["borderline"] == 0
    assert d["evidence_gate_state_counts"]["insufficient"] == 0
    assert len(d["evidence_gate_documents"]) == 7
    assert all(r["decision"] == "sufficient" for r in d["evidence_gate_documents"])


def test_per_doc_record_ordering_preserves_insertion() -> None:
    """R-020.11: per-doc ordering follows the iteration order of the
    caller (typically alphabetical by document_id from corpus_run.py).
    The RunSummary doesn't re-sort; it preserves the insertion order
    the caller built."""
    documents = [
        _make_record("inv_002_easy", "sufficient"),
        _make_record("inv_001_easy", "sufficient"),  # Out of alphabetic order intentionally
        _make_record("inv_010_medium", "borderline"),
    ]
    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=3, documents_succeeded=3,
        documents_failed=0,
        evidence_gate_state_counts={"sufficient": 2, "borderline": 1, "insufficient": 0},
        evidence_gate_documents=documents,
    )
    d = rs.to_dict()
    document_ids = [r["document_id"] for r in d["evidence_gate_documents"]]
    # Insertion order preserved — RunSummary does not sort.
    assert document_ids == ["inv_002_easy", "inv_001_easy", "inv_010_medium"]
