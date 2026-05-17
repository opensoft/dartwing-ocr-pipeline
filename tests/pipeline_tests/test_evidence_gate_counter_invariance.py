"""Feature 020 / T052a / US6 (FR-023):
counter invariance between the evidence gate and the prior
fallback-count features (018: region_strategy_fallback_count,
019: ocr_only_fallback_count).

FR-023: the evidence gate MUST NOT alter, suppress, or shadow either
fallback counter. Symmetrically, feature 018's region-strategy fallback
path MUST NOT alter the evidence-gate state counts (the gate is a pure
read; the fallback path is the writer for its own counter and never
the gate's counters).

These tests construct a ``RunSummary`` with non-zero starting values
on the cross-feature counters and assert that the serialized
``run_summary.to_dict()`` preserves them — the serializer's defense-
in-depth coercion in ``timing.py`` must not zero out, drop, or mutate
any value the caller provided.

CPU-safe: pure dataclass + serializer arithmetic, no pipeline run, no
Paddle, no GPU.
"""

from __future__ import annotations

from dartwing_ocr.pipeline.timing import RunSummary
from dartwing_ocr.preprocessing.evidence_gate import (
    EvidenceGateResult,
    FiveSignalSet,
    build_evidence_gate_document_record,
    evaluate_evidence_gate,
)


def _build_run_summary_with_nonzero_fallback_counts() -> RunSummary:
    """A RunSummary that starts with non-zero feature 018 / 019 fallback
    counters AND non-empty evidence_gate state. The default-zero values
    on each side are NOT the invariant under test — the invariant is
    that each side's writer does not stomp the other's value."""
    documents = [
        build_evidence_gate_document_record(
            document_id="inv_001_easy",
            result=EvidenceGateResult(
                signals=FiveSignalSet(
                    vendor_name_candidate_count=3,
                    header_band_token_density=14,
                    ocr_detection_confidence_mean=0.84,
                    business_suffix_present=True,
                    tax_id_shaped_present=False,
                ),
                decision="sufficient",
                evidence_gate_id="v1",
            ),
        )
    ]
    return RunSummary(
        stack_preset="cpu",
        resolved_profiles={},
        execution_slice={},
        on_failure="abort",
        documents_total=3,
        documents_succeeded=3,
        documents_failed=0,
        # Non-zero starting values on feature 018 / 019 counters; the
        # gate-aggregation serializer path must not touch them.
        region_strategy_fallback_count=2,
        ocr_only_fallback_count=1,
        # Non-zero evidence_gate state — exercise both the state_counts
        # coercion and the per-doc documents array.
        evidence_gate_state_counts={
            "sufficient": 1,
            "borderline": 0,
            "insufficient": 0,
        },
        evidence_gate_documents=documents,
    )


def test_fr023_evidence_gate_serializer_preserves_018_019_counters() -> None:
    """FR-023 forward direction: when the gate has non-empty state, the
    serializer MUST NOT alter / suppress / shadow feature 018's
    ``region_strategy_fallback_count`` or feature 019's
    ``ocr_only_fallback_count``.
    """
    rs = _build_run_summary_with_nonzero_fallback_counts()
    d = rs.to_dict()

    # Feature 018 counter survives the gate-aggregation path.
    assert d["region_strategy_fallback_count"] == 2, (
        "FR-023 violation: gate aggregation altered feature 018 "
        f"region_strategy_fallback_count from 2 to {d['region_strategy_fallback_count']!r}"
    )
    # Feature 019 counter survives the gate-aggregation path.
    assert d["ocr_only_fallback_count"] == 1, (
        "FR-023 violation: gate aggregation altered feature 019 "
        f"ocr_only_fallback_count from 1 to {d['ocr_only_fallback_count']!r}"
    )

    # Belt-and-braces: the gate state itself round-trips intact.
    assert d["evidence_gate_state_counts"] == {
        "sufficient": 1,
        "borderline": 0,
        "insufficient": 0,
    }
    assert len(d["evidence_gate_documents"]) == 1


def test_fr023_018_019_writers_do_not_alter_gate_counters() -> None:
    """FR-023 reverse direction: bumping the feature 018 / 019 counters
    on an already-constructed RunSummary MUST NOT mutate the
    evidence_gate state counts or documents array. We simulate the
    feature 018 / 019 writers by setting their fields directly on the
    dataclass instance (the orchestrators in corpus_run.py do this via
    keyword args at construction time; mutation after the fact is the
    strictest test of independence).
    """
    rs = _build_run_summary_with_nonzero_fallback_counts()

    # Snapshot the gate state BEFORE the simulated feature 018 / 019 writes.
    gate_state_before = dict(rs.evidence_gate_state_counts)
    gate_documents_before = list(rs.evidence_gate_documents)
    gate_suppressed_before = rs.evidence_gate_suppressed_fallback_count
    gate_id_before = rs.evidence_gate_id

    # Simulate feature 018 / 019 fallback firings AFTER gate state is set.
    rs.region_strategy_fallback_count += 5
    rs.ocr_only_fallback_count += 7

    # Gate state MUST be unchanged — neither feature 018 nor 019 owns
    # any evidence_gate_* field (FR-023).
    assert rs.evidence_gate_state_counts == gate_state_before
    assert rs.evidence_gate_documents == gate_documents_before
    assert rs.evidence_gate_suppressed_fallback_count == gate_suppressed_before
    assert rs.evidence_gate_id == gate_id_before

    # And the wire-format reflects the updated 018 / 019 counters
    # together with the unchanged gate state.
    d = rs.to_dict()
    assert d["region_strategy_fallback_count"] == 7
    assert d["ocr_only_fallback_count"] == 8
    assert d["evidence_gate_state_counts"] == gate_state_before
    assert len(d["evidence_gate_documents"]) == len(gate_documents_before)


def test_fr023_gate_pure_function_does_not_touch_runsummary_counters() -> None:
    """FR-023 deeper invariant: ``evaluate_evidence_gate`` is a pure
    function over a ``preprocess_output`` dict. Running it must not
    touch any module-level state, any RunSummary, or any other shared
    object — so a RunSummary's existing 018 / 019 counters survive
    multiple gate evaluations interleaved with counter writes.
    """
    rs = RunSummary(
        stack_preset="cpu",
        resolved_profiles={},
        execution_slice={},
        on_failure="abort",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
        region_strategy_fallback_count=2,
        ocr_only_fallback_count=1,
    )

    # Minimal preprocess_output dict that exercises the gate body.
    pp = {
        "pages": [
            {
                "page_number": 1,
                "width": 850,
                "height": 1100,
                "blocks": [
                    {
                        "bbox": [10, 5, 200, 30],
                        "text": "Acme Corp.",
                        "confidence": 0.92,
                    }
                ],
            }
        ]
    }

    # Run the gate three times; mutate counters between each run.
    for i in range(3):
        result = evaluate_evidence_gate(pp)
        assert result.evidence_gate_id == "v1"
        rs.region_strategy_fallback_count += 1
        rs.ocr_only_fallback_count += 1

    # 2 + 3 = 5; 1 + 3 = 4. The gate did not touch either counter.
    assert rs.region_strategy_fallback_count == 5
    assert rs.ocr_only_fallback_count == 4
