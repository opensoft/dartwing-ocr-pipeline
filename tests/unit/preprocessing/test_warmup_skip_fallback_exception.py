"""Feature 020 + 021 / FR-007 + FR-009 warmup exception.

When --gpu-warmup AND --evidence-gate-skip-fallback AND
--preprocess-strategy=ocr-only-v1 are all active,
``run_warmup_if_active`` constructs PPStructureV3 in addition to OCR-only
— the operator-opt-in trade-off documented in the lazy-construction clause.

This file holds two layers of coverage:

1. **CPU-safe (feature 020)**: monkeypatches the heavyweight constructors
   so the wiring tests exercise the dispatch logic without invoking
   PaddleOCR. These run unconditionally on CPU CI.

2. **GPU end-to-end (feature 021 T012)**: `test_warmup_forces_ppstructurev3_
   construction_under_skip_fallback_gpu` — runs the actual pipeline via
   subprocess on a real corpus document and asserts the warmup phase key
   appears in `run_summary`. Cross-checks the CPU monkey-patched logic
   against real GPU runtime behavior. Skipped on CPU by the root-conftest
   `pytest_collection_modifyitems` gate.

The CPU layer is fast (~50ms) and covers the dispatch logic; the GPU layer
is slow (60-120s per run) and covers the wiring + real engine construction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dartwing_ocr.preprocessing import pipeline as _pipeline_mod

# Multi-agent-review MED-1 fix: `tests.pipeline_tests.gpu_helpers` is documented
# at gpu_helpers.py module top as "imported by pytest.mark.gpu-marked tests only".
# This file's 4 CPU mock tests do NOT need it. Importing it at module top would
# violate the invariant and create a future-import-time-side-effect risk that
# could break CPU collection. The 1 GPU test below imports the helpers inside
# its function body so CPU collection never triggers the import path.


class _Calls:
    def __init__(self) -> None:
        self.ocr_only_constructed = 0
        self.ppstructurev3_constructed = 0
        self.warmups: list[str] = []


@pytest.fixture
def fake_engines(monkeypatch: pytest.MonkeyPatch) -> _Calls:
    calls = _Calls()

    monkeypatch.setattr(_pipeline_mod, "is_gpu_lane", lambda _lane: True)

    from dartwing_ocr.preprocessing import ocr as _ocr_mod, warmup as _warmup_mod

    def _fake_ensure_gpu_ready(**_kwargs: Any) -> None:
        calls.ppstructurev3_constructed += 1

    def _fake_run_warmup(engine: Any) -> None:
        calls.warmups.append(type(engine).__name__)

    def _fake_get_active_engine() -> Any:
        return type("PPStructureV3Stub", (), {})()

    monkeypatch.setattr(
        "dartwing_ocr.preprocessing.preflight.ensure_gpu_ready",
        _fake_ensure_gpu_ready,
    )
    monkeypatch.setattr(_warmup_mod, "run_warmup", _fake_run_warmup)
    monkeypatch.setattr(_ocr_mod, "get_active_engine", _fake_get_active_engine)

    from dartwing_ocr.preprocessing import ocr_only as _ocr_only_mod

    def _fake_get_ocr_engine(**_kwargs: Any) -> None:
        calls.ocr_only_constructed += 1

    def _fake_get_active_ocr_engine() -> Any:
        return type("OcrOnlyStub", (), {})()

    monkeypatch.setattr(_ocr_only_mod, "_get_ocr_engine", _fake_get_ocr_engine)
    monkeypatch.setattr(
        _ocr_only_mod, "get_active_ocr_engine", _fake_get_active_ocr_engine
    )

    return calls


def test_warmup_ocr_only_alone_does_not_construct_ppstructurev3(
    fake_engines: _Calls,
) -> None:
    _pipeline_mod.run_warmup_if_active(
        preprocess_lane="gpu0",
        warmup_optin=True,
        preprocess_strategy_id="ocr-only-v1",
        evidence_gate_skip_fallback_optin=False,
    )
    assert fake_engines.ocr_only_constructed == 1
    assert fake_engines.ppstructurev3_constructed == 0


def test_warmup_ocr_only_with_skip_fallback_also_constructs_ppstructurev3(
    fake_engines: _Calls,
) -> None:
    _pipeline_mod.run_warmup_if_active(
        preprocess_lane="gpu0",
        warmup_optin=True,
        preprocess_strategy_id="ocr-only-v1",
        evidence_gate_skip_fallback_optin=True,
    )
    assert fake_engines.ocr_only_constructed == 1
    assert fake_engines.ppstructurev3_constructed == 1
    assert len(fake_engines.warmups) == 2


def test_warmup_ppstructurev3_strategy_ignores_skip_fallback_optin(
    fake_engines: _Calls,
) -> None:
    _pipeline_mod.run_warmup_if_active(
        preprocess_lane="gpu0",
        warmup_optin=True,
        preprocess_strategy_id=None,
        evidence_gate_skip_fallback_optin=True,
    )
    assert fake_engines.ocr_only_constructed == 0
    assert fake_engines.ppstructurev3_constructed == 1


def test_warmup_skipped_when_optin_off(fake_engines: _Calls) -> None:
    _pipeline_mod.run_warmup_if_active(
        preprocess_lane="gpu0",
        warmup_optin=False,
        preprocess_strategy_id="ocr-only-v1",
        evidence_gate_skip_fallback_optin=True,
    )
    assert fake_engines.ocr_only_constructed == 0
    assert fake_engines.ppstructurev3_constructed == 0


# ---------------------------------------------------------------------------
# Feature 021 T012 / FR-009 GPU end-to-end variant
# ---------------------------------------------------------------------------


@pytest.mark.gpu
def test_warmup_forces_ppstructurev3_construction_under_skip_fallback_gpu(
    tmp_path: Path,
) -> None:
    """FR-009 end-to-end: `--gpu-warmup` + `--evidence-gate-skip-fallback` +
    `ocr-only-v1` on a real `sufficient` document forces PPStructureV3
    construction (warmup phase key present in `run_summary`), even though
    the document is later suppressed by skip-fallback. Cross-checks the
    CPU monkey-patched dispatch logic above against real GPU runtime.

    Skipped on CPU by the root-conftest gate.
    """
    # Deferred import (MED-1): only imports gpu_helpers when this GPU test
    # actually runs on a GPU host. CPU collection (root-conftest skip-gate)
    # never reaches this point, so the import never fires on CPU.
    from tests.pipeline_tests.gpu_helpers import (
        extract_run_summary,
        find_evidence_gate_record,
        find_per_document_record,
        invoke_pipeline,
        phase_keys,
        setup_scratch_corpus,
    )

    doc_id = "inv_001_easy"
    documents_file, _ = setup_scratch_corpus(scratch_root=tmp_path, doc_ids=[doc_id])

    result = invoke_pipeline(
        documents_file=documents_file,
        extra_flags=["--evidence-gate-skip-fallback", "--gpu-warmup"],
    )

    assert result.returncode == 0, (
        f"pipeline failed (exit {result.returncode}); stderr=\n{result.stderr}"
    )

    summary = extract_run_summary(result.stdout)
    gate_doc = find_evidence_gate_record(summary, doc_id)
    per_doc = find_per_document_record(summary, doc_id)

    # Precondition: the doc IS sufficient (otherwise skip-fallback wouldn't
    # suppress; the test scenario would still hold trivially but the
    # operator should know).
    assert gate_doc.get("decision") == "sufficient", (
        f"corpus precondition: {doc_id} decision={gate_doc.get('decision')!r}, "
        f"expected 'sufficient'. Test scenario is FR-009 (warmup with all-"
        f"sufficient skip-fallback)."
    )

    # Suppression counter incremented (skip-fallback still suppressed the
    # OCR-only candidate — warmup did NOT short-circuit suppression).
    assert summary.get("evidence_gate_suppressed_fallback_count") == 1, (
        f"FR-009 invariant: skip-fallback suppression unaffected by warmup; "
        f"expected count=1, got "
        f"{summary.get('evidence_gate_suppressed_fallback_count')!r}"
    )

    # Core FR-009 assertion: warmup phase key MUST appear despite the doc
    # being suppressed — `--gpu-warmup` is the explicit operator trade-off
    # that constructs PPStructureV3 unconditionally on the lane.
    keys = phase_keys(per_doc)
    assert "warmup" in keys, (
        f"FR-009 violation: `--gpu-warmup` was passed alongside "
        f"`--evidence-gate-skip-fallback`, but phase_timings.warmup is absent "
        f"from the per-doc record. PPStructureV3 was not constructed. "
        f"This contradicts the explicit operator trade-off of `--gpu-warmup`. "
        f"phase keys present: {sorted(keys)!r}"
    )
