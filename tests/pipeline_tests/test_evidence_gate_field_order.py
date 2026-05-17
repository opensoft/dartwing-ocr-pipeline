"""Feature 020 / T024 / R-020.10 / contracts/run-summary-schema.md
§Order of keys: deterministic field-order test.

Verifies the four new feature 020 fields are emitted in the exact
documented order AFTER feature 019's two fields. This is the single
authoritative test for the wire-format key ordering; broader presence /
default-value assertions live in ``test_run_summary_schema_0_1_7.py``.
"""

from __future__ import annotations

from dartwing_ocr.pipeline.timing import RunSummary


def test_exact_four_field_order() -> None:
    """The four new fields are emitted in this exact order:

    1. ``evidence_gate_id``
    2. ``evidence_gate_state_counts``
    3. ``evidence_gate_documents``
    4. ``evidence_gate_suppressed_fallback_count``
    """
    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=0, documents_succeeded=0,
        documents_failed=0,
    )
    keys = list(rs.to_dict().keys())
    feature_020_keys = [k for k in keys if k.startswith("evidence_gate")]
    assert feature_020_keys == [
        "evidence_gate_id",
        "evidence_gate_state_counts",
        "evidence_gate_documents",
        "evidence_gate_suppressed_fallback_count",
    ]


def test_feature_020_keys_appear_after_feature_019_keys() -> None:
    """The four new fields come strictly AFTER feature 019's two fields
    in the wire format."""
    rs = RunSummary(
        stack_preset="cpu", resolved_profiles={}, execution_slice={},
        on_failure="abort", documents_total=0, documents_succeeded=0,
        documents_failed=0,
    )
    keys = list(rs.to_dict().keys())
    last_019_index = max(
        keys.index("preprocess_strategy_id"),
        keys.index("ocr_only_fallback_count"),
    )
    first_020_index = min(
        keys.index(k) for k in keys if k.startswith("evidence_gate")
    )
    assert first_020_index > last_019_index
