"""Table-driven classifier tests (T010 / FR-001).

Mocks the paddle/paddleocr surface to drive each FR-001 state through
`classify(...)` and asserts the returned `PreflightReadout.state` plus
the data-model-mandated evidence presence rules.

VT-003 / T035: this test module exists to test the preflight classifier
itself, so it is `pytest.importorskip`-gated on the preflight module.
When preflight.py is temporarily unavailable (collection-time defensive
path verification), the entire module is skipped rather than erroring.
"""
from __future__ import annotations

import sys
from importlib import metadata
from types import SimpleNamespace
from typing import Optional

import pytest

# Feature 014 (VT-003 / T035): skip the whole module if preflight.py
# is unavailable (the collection-time defensive path requires zero
# ERROR entries).
preflight = pytest.importorskip("ledgerlinc_ocr.preprocessing.preflight")
PreflightEvidence = preflight.PreflightEvidence
PreflightReadout = preflight.PreflightReadout
PreflightState = preflight.PreflightState
classify = preflight.classify


def _stub_paddle(*, cuda: bool, rocm: bool, device_count: int, bind_raises: bool = False, init_raises: bool = False, init_seconds: Optional[float] = None):
    """Build a minimal `paddle` stand-in module exposing only the
    surface `classify()` calls."""

    class _CudaNamespace:
        @staticmethod
        def device_count() -> int:
            return device_count

    class _DeviceNamespace:
        cuda = _CudaNamespace()

        @staticmethod
        def set_device(device: str) -> None:
            if bind_raises:
                raise RuntimeError(f"can't bind {device}")

    def _to_tensor(_):
        if bind_raises:
            raise RuntimeError("can't bind tensor")

        class _T:
            pass

        return _T()

    def _is_compiled_with_cuda() -> bool:
        return cuda

    def _is_compiled_with_rocm() -> bool:
        return rocm

    return SimpleNamespace(
        is_compiled_with_cuda=_is_compiled_with_cuda,
        is_compiled_with_rocm=_is_compiled_with_rocm,
        device=_DeviceNamespace,
        to_tensor=_to_tensor,
    )


def _patch_paddle(monkeypatch, paddle_stub):
    monkeypatch.setitem(sys.modules, "paddle", paddle_stub)


def _patch_versions_present(monkeypatch):
    """Make `_package_version` return non-None for paddle/paddleocr."""
    real_version = metadata.version

    def fake_version(name: str) -> str:
        if name == "paddlepaddle":
            return "3.3.1"
        if name == "paddleocr":
            return "3.5.0"
        return real_version(name)

    monkeypatch.setattr(metadata, "version", fake_version)


def _patch_versions_absent(monkeypatch):
    """Make `_package_version` raise PackageNotFoundError for paddle/paddleocr."""
    real_version = metadata.version

    def fake_version(name: str) -> str:
        if name in ("paddlepaddle", "paddleocr"):
            raise metadata.PackageNotFoundError(name)
        return real_version(name)

    monkeypatch.setattr(metadata, "version", fake_version)


def test_state_a_paddle_not_installed(monkeypatch) -> None:
    _patch_versions_absent(monkeypatch)
    readout = classify(attempt_ppstructurev3_init=False)
    assert readout.state is PreflightState.PADDLE_NOT_INSTALLED
    assert readout.evidence.paddle_version is None
    assert readout.evidence.paddleocr_version is None
    # All three init fields are None when paddle import failed.
    assert readout.evidence.ppstructurev3_init_seconds is None
    assert readout.evidence.ppstructurev3_init_error is None
    assert readout.evidence.ppstructurev3_init_skipped_reason is None


def test_state_b_paddle_cpu_only(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle(cuda=False, rocm=False, device_count=0))
    readout = classify(attempt_ppstructurev3_init=False)
    assert readout.state is PreflightState.PADDLE_CPU_ONLY
    assert readout.evidence.paddle_compiled_with_cuda is False
    assert readout.evidence.paddle_compiled_with_rocm is False


def test_state_c_gpu_not_exposed(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle(cuda=False, rocm=True, device_count=0))
    readout = classify(attempt_ppstructurev3_init=False)
    assert readout.state is PreflightState.GPU_NOT_EXPOSED
    assert readout.evidence.visible_device_count == 0
    assert readout.evidence.paddle_compiled_with_rocm is True


def test_state_d_gpu_exposed_paddle_cant_bind(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(
        monkeypatch,
        _stub_paddle(cuda=True, rocm=False, device_count=1, bind_raises=True),
    )
    readout = classify(attempt_ppstructurev3_init=False)
    assert readout.state is PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND
    assert readout.evidence.visible_device_count == 1
    assert readout.evidence.ppstructurev3_init_error is not None


def test_state_e_ppstructurev3_init_failed(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle(cuda=True, rocm=False, device_count=1))

    class _BrokenPPStructure:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("HipErrorNoBinaryForGpu")

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=_BrokenPPStructure))
    readout = classify(attempt_ppstructurev3_init=True)
    assert readout.state is PreflightState.PPSTRUCTUREV3_INIT_FAILED
    assert readout.evidence.ppstructurev3_init_error is not None
    assert "HipErrorNoBinaryForGpu" in readout.evidence.ppstructurev3_init_error


def test_state_f_ppstructurev3_init_succeeded(monkeypatch) -> None:
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle(cuda=True, rocm=False, device_count=1))

    class _OkPPStructure:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(PPStructureV3=_OkPPStructure))
    readout = classify(attempt_ppstructurev3_init=True)
    assert readout.state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED
    # Data-model rule: selected_device matches gpu:N when state is succeeded.
    assert readout.evidence.selected_device is not None
    assert readout.evidence.selected_device.startswith("gpu:")
    # Init time was recorded.
    assert readout.evidence.ppstructurev3_init_seconds is not None
    # Skipped reason and error are mutually exclusive with seconds.
    assert readout.evidence.ppstructurev3_init_error is None
    assert readout.evidence.ppstructurev3_init_skipped_reason is None


def test_recommendation_references_doc_for_each_fail_state(monkeypatch) -> None:
    """Per FR-003 three-part rule: every fail-state recommendation
    must reference docs/stage1-vendor-identity/paddle-gpu-preflight.md."""
    doc_substring = "paddle-gpu-preflight.md"

    # PADDLE_NOT_INSTALLED
    _patch_versions_absent(monkeypatch)
    r1 = classify(attempt_ppstructurev3_init=False)
    assert doc_substring in r1.recommendation

    # PADDLE_CPU_ONLY
    _patch_versions_present(monkeypatch)
    _patch_paddle(monkeypatch, _stub_paddle(cuda=False, rocm=False, device_count=0))
    r2 = classify(attempt_ppstructurev3_init=False)
    assert doc_substring in r2.recommendation

    # GPU_NOT_EXPOSED
    _patch_paddle(monkeypatch, _stub_paddle(cuda=False, rocm=True, device_count=0))
    r3 = classify(attempt_ppstructurev3_init=False)
    assert doc_substring in r3.recommendation


def test_evidence_dataclass_validation_rules() -> None:
    """Sanity check: PreflightEvidence is a frozen dataclass; its
    fields are immutable post-construction."""
    ev = PreflightEvidence(
        interpreter_path="/usr/bin/python",
        interpreter_version="3.12.0",
        venv_path=None,
        paddle_version=None,
        paddleocr_version=None,
        paddle_compiled_with_cuda=None,
        paddle_compiled_with_rocm=None,
        visible_device_count=None,
        selected_device=None,
        runtime_device_exposure={},
    )
    with pytest.raises((AttributeError, TypeError)):
        ev.interpreter_path = "/usr/bin/python3.13"  # type: ignore[misc]


def test_state_enum_values_are_normative() -> None:
    """Per Research R-014.3 / Contracts §1: enum string values are the
    normative FR-001 vocabulary used in JSON, error messages, exit
    codes, and pytest skip reasons."""
    assert PreflightState.PADDLE_NOT_INSTALLED.value == "paddle_not_installed"
    assert PreflightState.PADDLE_CPU_ONLY.value == "paddle_cpu_only"
    assert PreflightState.GPU_NOT_EXPOSED.value == "gpu_not_exposed"
    assert PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND.value == "gpu_exposed_paddle_cant_bind"
    assert PreflightState.PPSTRUCTUREV3_INIT_FAILED.value == "ppstructurev3_init_failed"
    assert PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED.value == "ppstructurev3_init_succeeded"


def test_readout_serializers_round_trip(monkeypatch) -> None:
    """to_text + to_json_dict are stable on a known input."""
    _patch_versions_absent(monkeypatch)
    readout = classify(attempt_ppstructurev3_init=False)
    text = readout.to_text()
    assert isinstance(text, str)
    assert "[preflight] state:" in text
    assert "recommendation:" in text
    payload = readout.to_json_dict()
    assert payload["kind"] == "preflight_readout"
    assert payload["schema_version"] == "0.1.0"
    assert payload["state"] == readout.state.value
    assert "evidence" in payload
    assert "recommendation" in payload
