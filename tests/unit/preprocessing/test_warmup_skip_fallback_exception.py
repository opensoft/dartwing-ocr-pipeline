"""Feature 020 / FR-007 exception: when --gpu-warmup AND
--evidence-gate-skip-fallback AND --preprocess-strategy=ocr-only-v1 are
all active, ``run_warmup_if_active`` constructs PPStructureV3 in addition
to OCR-only — the operator-opt-in trade-off documented in the lazy-
construction clause.

CPU-safe: monkeypatches the heavyweight constructors so the test exercises
the wiring without invoking PaddleOCR.
"""

from __future__ import annotations

from typing import Any

import pytest

from dartwing_ocr.preprocessing import pipeline as _pipeline_mod


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
