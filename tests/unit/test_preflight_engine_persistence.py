"""Engine persistence + single-device guard tests (feature 015 / T002).

Covers four invariants from `contracts/module-invariants.md`:

- CF5 — after `classify(attempt_ppstructurev3_init=True)` returns
  `PPSTRUCTUREV3_INIT_SUCCEEDED`, `id(ocr._ENGINE)` equals the engine
  classify built (verifies engine adoption per R-015.1).
- CF6 — after `classify(attempt_ppstructurev3_init=False)`, `ocr._ENGINE`
  remains None (the --no-init path MUST NOT touch the runtime singleton).
- CF4 — after CF5 succeeds, `ocr._get_engine(device="cpu")` raises
  `RuntimeError` (single-device-per-process guard preserved).
- FF2 — after a successful first `ensure_gpu_ready()`, a second call
  short-circuits via the `_LAST_READOUT` cache without reconstructing
  PPStructureV3 (constructor `call_count == 1` after both calls).
"""
from __future__ import annotations

import sys
from importlib import metadata
from types import SimpleNamespace
from typing import Optional

import pytest


preflight = pytest.importorskip("ledgerlinc_ocr.preprocessing.preflight")
ocr = pytest.importorskip("ledgerlinc_ocr.preprocessing.ocr")
PreflightState = preflight.PreflightState
classify = preflight.classify
ensure_gpu_ready = preflight.ensure_gpu_ready


def _stub_paddle(*, cuda: bool = True, rocm: bool = False, device_count: int = 1):
    class _CudaNamespace:
        @staticmethod
        def device_count() -> int:
            return device_count

    class _DeviceNamespace:
        cuda = _CudaNamespace()

        @staticmethod
        def set_device(device: str) -> None:
            return None

    def _to_tensor(_):
        class _T:
            pass

        return _T()

    def _seed(_):
        return None

    return SimpleNamespace(
        is_compiled_with_cuda=lambda: cuda,
        is_compiled_with_rocm=lambda: rocm,
        device=_DeviceNamespace,
        to_tensor=_to_tensor,
        seed=_seed,
    )


def _patch_paddle(monkeypatch, paddle_stub) -> None:
    monkeypatch.setitem(sys.modules, "paddle", paddle_stub)


def _patch_versions_present(monkeypatch) -> None:
    real_version = metadata.version

    def fake_version(name: str) -> str:
        if name == "paddlepaddle":
            return "3.3.1"
        if name == "paddleocr":
            return "3.5.0"
        return real_version(name)

    monkeypatch.setattr(metadata, "version", fake_version)


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Clear engine + preflight cache before every test in this module."""
    ocr._ENGINE = None
    ocr._ENGINE_DEVICE = None
    ocr._PADDLE_SEEDED = False
    if hasattr(ocr, "reset_gpu_inference_ns"):
        ocr.reset_gpu_inference_ns()
    if hasattr(preflight, "reset_cache"):
        preflight.reset_cache()
    yield
    ocr._ENGINE = None
    ocr._ENGINE_DEVICE = None
    ocr._PADDLE_SEEDED = False


# ---------------------------------------------------------------------------
# CF5 — engine adoption
# ---------------------------------------------------------------------------

def test_cf5_classify_with_init_persists_engine_into_ocr_module(monkeypatch) -> None:
    """After successful classify-with-init, ocr._ENGINE MUST be the engine
    classify built (same id), and ocr._ENGINE_DEVICE MUST equal "gpu:0"."""
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle())

    captured = {}

    class _CapturePPStructure:
        def __init__(self, *args, **kwargs):
            captured["engine_id"] = id(self)

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=_CapturePPStructure))

    readout = classify(attempt_ppstructurev3_init=True)

    assert readout.state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
    assert ocr._ENGINE is not None, "CF5: classify must persist engine into ocr._ENGINE"
    assert id(ocr._ENGINE) == captured["engine_id"], (
        "CF5: ocr._ENGINE must be the same instance classify built (not a fresh one)"
    )
    assert ocr._ENGINE_DEVICE == "gpu:0", "CF5: device must be locked to gpu:0"


# ---------------------------------------------------------------------------
# CF6 — --no-init MUST NOT touch ocr._ENGINE
# ---------------------------------------------------------------------------

def test_cf6_classify_no_init_does_not_touch_engine(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle())

    construction_calls = {"count": 0}

    class _ShouldNotConstruct:
        def __init__(self, *args, **kwargs):
            construction_calls["count"] += 1

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=_ShouldNotConstruct))

    readout = classify(attempt_ppstructurev3_init=False)

    assert readout.state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
    assert construction_calls["count"] == 0, "CF6: --no-init must not construct PPStructureV3"
    assert ocr._ENGINE is None, "CF6: --no-init must leave ocr._ENGINE untouched"
    assert ocr._ENGINE_DEVICE is None, "CF6: --no-init must leave ocr._ENGINE_DEVICE untouched"


# ---------------------------------------------------------------------------
# CF4 — single-device-per-process guard preserved
# ---------------------------------------------------------------------------

def test_cf4_second_device_after_engine_bound_raises(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle())

    class _OkPPStructure:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=_OkPPStructure))

    classify(attempt_ppstructurev3_init=True)
    assert ocr._ENGINE is not None
    assert ocr._ENGINE_DEVICE == "gpu:0"

    with pytest.raises(RuntimeError, match="single-device-per-process|already constructed"):
        ocr._get_engine(device="cpu")


# ---------------------------------------------------------------------------
# FF2 — second ensure_gpu_ready short-circuits via cache
# ---------------------------------------------------------------------------

def test_ff2_second_ensure_gpu_ready_short_circuits_no_reconstruction(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle())

    construction_calls = {"count": 0}

    class _CountingPPStructure:
        def __init__(self, *args, **kwargs):
            construction_calls["count"] += 1

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=_CountingPPStructure))

    readout1 = ensure_gpu_ready()
    readout2 = ensure_gpu_ready()

    assert readout1.state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
    assert readout2.state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
    assert construction_calls["count"] == 1, (
        "FF2: second ensure_gpu_ready() must short-circuit on _LAST_READOUT cache "
        f"(constructor was called {construction_calls['count']} times, expected 1)"
    )
    # Same readout instance should be returned (cache short-circuit).
    assert readout1 is readout2, "FF2: cached readout must be returned by reference"
