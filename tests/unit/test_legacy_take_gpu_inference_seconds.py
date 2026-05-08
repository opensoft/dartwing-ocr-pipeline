"""Legacy `take_gpu_inference_seconds()` back-compat test (T037 / R-015.3).

Feature 015 reshaped the per-page accumulator to a list of
`(page_number, ns)` tuples. The legacy `take_gpu_inference_seconds()`
helper is preserved as a back-compat sum wrapper for one schema
version — any external caller built against feature 014 should
continue to receive the same scalar-seconds return value.

Asserts:

- Empty accumulator → returns None.
- After recording two pages, returns the sum of seconds.
- After draining, the accumulator is reset (next call returns None).
- The sum equals the sum of seconds returned by `take_gpu_inference_per_page()`
  (i.e., both helpers drain the same underlying list).
"""
from __future__ import annotations

import pytest


ocr = pytest.importorskip("ledgerlinc_ocr.preprocessing.ocr")


@pytest.fixture(autouse=True)
def _reset_per_test():
    ocr.reset_gpu_inference_ns()
    yield
    ocr.reset_gpu_inference_ns()


def test_t037_empty_returns_none() -> None:
    assert ocr.take_gpu_inference_seconds() is None


def test_t037_sum_after_two_pages() -> None:
    ocr._record_gpu_inference_ns(1, 500_000_000)  # page 1, 0.5 s
    ocr._record_gpu_inference_ns(2, 250_000_000)  # page 2, 0.25 s
    seconds = ocr.take_gpu_inference_seconds()
    assert seconds is not None
    assert abs(seconds - 0.75) < 1e-6


def test_t037_drains_and_resets_accumulator() -> None:
    ocr._record_gpu_inference_ns(1, 500_000_000)
    first = ocr.take_gpu_inference_seconds()
    assert first is not None
    second = ocr.take_gpu_inference_seconds()
    assert second is None, "legacy helper must drain on first call"


def test_t037_legacy_sum_equals_new_helper_sum() -> None:
    """take_gpu_inference_seconds() and sum-of-take_gpu_inference_per_page()
    return identical totals when both drain the same accumulator state.
    Run twice (alternating drain helpers) to confirm."""
    ocr._record_gpu_inference_ns(1, 500_000_000)
    ocr._record_gpu_inference_ns(2, 250_000_000)
    legacy = ocr.take_gpu_inference_seconds()

    ocr._record_gpu_inference_ns(1, 500_000_000)
    ocr._record_gpu_inference_ns(2, 250_000_000)
    new_per_page = ocr.take_gpu_inference_per_page()
    assert new_per_page is not None
    new_sum = round(sum(s for _, s in new_per_page), 6)

    assert abs((legacy or 0.0) - new_sum) < 1e-6, (
        f"legacy sum ({legacy}) must equal sum of new per-page helper ({new_sum})"
    )
