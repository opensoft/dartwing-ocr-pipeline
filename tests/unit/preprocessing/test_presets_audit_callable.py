"""Feature 017 (T013): CPU-safe unit tests for the audit callable's
result inspection logic.

Per R-017.7 / Plan §I-6: the audit callable inspects PPStructureV3
predict results and returns a sorted subset of
`AUDIT_SUB_MODULE_VOCABULARY`, silently dropping unknown sub-module
keys. These tests verify the inspector via a stub engine that returns
mock predict results — no real Paddle/PaddleOCR engine, no GPU, no
fixture loading.
"""
from __future__ import annotations

from ledgerlinc_ocr.preprocessing.identifiers import AUDIT_SUB_MODULE_VOCABULARY
from ledgerlinc_ocr.preprocessing.presets import (
    _audit_identity_no_op,
    _inspect_predict_result,
)


# ---------------------------------------------------------------------------
# Plan §I-6: silently drop unknown sub-module names; sorted output
# ---------------------------------------------------------------------------


def test_audit_callable_returns_sorted_subset_of_closed_vocabulary() -> None:
    """A mock PPStructureV3 predict result list with known sub-module
    keys yields a lex-sorted list of known sub-module names — strict
    subset of AUDIT_SUB_MODULE_VOCABULARY (Plan §I-6 / R-017.7)."""
    mock_legacy = [
        {
            "layout_det_res": [...],
            "table_res": [...],
            "dt_polys": [...],
            "rec_texts": ["hello"],
        }
    ]
    out = _inspect_predict_result(mock_legacy)
    assert out == ["layout_detection", "ocr_det", "ocr_rec", "table_recognition"]
    assert set(out) <= set(AUDIT_SUB_MODULE_VOCABULARY)


def test_audit_callable_drops_unknown_keys() -> None:
    """Per R-017.7: unknown PaddleOCR sub-module names are silently
    dropped — protects against future PaddleOCR releases that introduce
    new keys."""
    mock_with_unknowns = [
        {
            "layout_det_res": [...],
            "frobnicate_results": [...],  # not in vocabulary — dropped
            "baz_v9_results": [...],  # not in vocabulary — dropped
            "rec_texts": ["hi"],
        }
    ]
    out = _inspect_predict_result(mock_with_unknowns)
    assert out == ["layout_detection", "ocr_rec"]


def test_audit_callable_handles_reduced_module_set_signature() -> None:
    """`reduced-v1` configuration: predict result lacks `table_res`,
    so the audit list lacks `table_recognition` (R-017.3 expected
    behavior; verified empirically against actual results in
    `research.md` Appendix B at landing)."""
    mock_reduced = [
        {
            "layout_det_res": [...],
            # No table_res — table recognition was disabled
            "dt_polys": [...],
            "rec_texts": ["hi"],
        }
    ]
    out = _inspect_predict_result(mock_reduced)
    assert "table_recognition" not in out
    assert set(out) == {"layout_detection", "ocr_det", "ocr_rec"}


def test_audit_callable_handles_empty_results() -> None:
    """An empty predict result list (no pages) returns an empty audit
    list — never raises."""
    assert _inspect_predict_result([]) == []
    assert _inspect_predict_result(None) == []


def test_audit_callable_handles_object_attribute_access() -> None:
    """Some PaddleOCR result objects expose attribute access rather
    than dict access. The inspector probes `dir()` for known names."""

    class _ObjectStyleResult:
        layout_det_res = "..."
        rec_texts = ["hello"]
        _private_internal = "ignored"

    out = _inspect_predict_result([_ObjectStyleResult()])
    # Both layout_det_res and rec_texts are AUDIT_SUB_MODULE_VOCABULARY signatures
    assert "layout_detection" in out
    assert "ocr_rec" in out


def test_audit_identity_no_op_returns_empty_list() -> None:
    """Per R-017.7 / Plan §I-6: CPU/stub identity-preset audit returns
    `[]` immediately without touching any engine — testable without a
    Paddle dependency. Distinct from "audit ran but found nothing"
    (which would be the same `[]` from a real predict on an empty
    document)."""
    sentinel = object()  # not callable, would raise if invoked
    assert _audit_identity_no_op(sentinel) == []


def test_audit_callable_output_is_subset_of_closed_vocabulary() -> None:
    """For any input, the audit output must be a subset of
    `AUDIT_SUB_MODULE_VOCABULARY` — invariant from Plan §I-6."""
    inputs = [
        [{"layout_det_res": []}],
        [{"random_unknown_key": []}],
        [{"layout_det_res": [], "table_res": [], "rec_texts": [], "dt_polys": []}],
        [],
        None,
    ]
    for inp in inputs:
        out = _inspect_predict_result(inp)
        assert set(out) <= set(AUDIT_SUB_MODULE_VOCABULARY)
        # Output is sorted (Plan §I-6)
        assert out == sorted(out)


def test_audit_callable_handles_multipage_results() -> None:
    """A multi-page predict result (one dict per page) consolidates
    sub-module signatures across pages — if any page invoked a
    sub-module, it's reported."""
    multipage = [
        {"layout_det_res": [...]},  # page 1 only had layout
        {"rec_texts": ["..."]},  # page 2 only had ocr_rec
        {"dt_polys": [...]},  # page 3 only had ocr_det
    ]
    out = _inspect_predict_result(multipage)
    assert set(out) == {"layout_detection", "ocr_det", "ocr_rec"}
