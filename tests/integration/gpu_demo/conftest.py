"""Shared pytest fixtures for the GPU MVP demo (feature 023) integration tests.

Provides CPU-isolated stubs per R-023.4 + R-023.5:

- :func:`paddle_preflight_stub` (T021): monkeypatches feature 014's preflight
  to return ``PreflightState.PASS_ROCM_GPU`` so the demo's `paddle-rocm-preflight`
  readiness check passes without booting Paddle on CI.
- :func:`ollama_http_stub` (T022): an ``httpx.MockTransport`` that responds
  to ``/api/ps`` and ``/api/version`` with canned payloads. Mounted into
  ``httpx.get`` via the demo's readiness modules — see the implementation
  inside each fixture for the monkey-patch target.
- :func:`ok_fixture_folder`: returns the path to ``fixtures/ok/`` (which has
  a real ``source.pdf`` symlink + a valid ``voter_config.yaml``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import httpx
import pytest


FIXTURES_ROOT = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Paddle ROCm preflight stub (T021)
# ---------------------------------------------------------------------------


class _StubPreflightReadout:
    """Stand-in for feature 014's ``PreflightReadout`` (pass-by-default)."""

    def __init__(self, state, recommendation: str = "") -> None:  # noqa: D401 — short helper
        self.state = state
        self.recommendation = recommendation


@pytest.fixture
def paddle_preflight_stub(monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch feature 014's ``preflight.classify`` to report success by default.

    Returns a setter the test can call to change the stubbed state mid-test
    (e.g., to exercise the FAIL path with a non-success state).
    """
    # Lazy import — only required when this fixture is requested.
    from dartwing_ocr.preprocessing import preflight as preflight_mod

    state = {
        "state": preflight_mod.PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED,
        "recommendation": "",
    }

    def _classify(**kwargs):  # type: ignore[no-redef]
        return _StubPreflightReadout(state["state"], state["recommendation"])

    monkeypatch.setattr(preflight_mod, "classify", _classify)

    def _set_state(new_state, recommendation: str = "") -> None:
        state["state"] = new_state
        state["recommendation"] = recommendation

    return _set_state


# ---------------------------------------------------------------------------
# Ollama HTTP stub (T022) — uses httpx.MockTransport via a monkeypatched
# httpx.get applied to the readiness modules that call /api/ps and
# /api/version directly.
# ---------------------------------------------------------------------------


def _default_handler(request: httpx.Request) -> httpx.Response:
    """Default canned responses: Ollama 0.4.5 with one fully-GPU-placed model."""
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.4.5"})
    if request.url.path == "/api/ps":
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "qwen2.5-vl:7b",
                        "size": 4906000000,
                        "size_vram": 4906000000,
                        "context_length": 2048,
                    }
                ]
            },
        )
    return httpx.Response(404, json={"error": f"no canned response for {request.url}"})


@pytest.fixture
def ollama_http_stub(monkeypatch: pytest.MonkeyPatch):
    """Replace ``httpx.get`` inside readiness modules with a MockTransport.

    The returned callable accepts an ``httpx.MockTransport`` handler, allowing
    individual tests to override the canned responses (e.g., for failure-path
    tests in US2/US3).
    """
    handler = {"fn": _default_handler}

    def _mock_get(url: str, timeout: float = 2.0, **_) -> httpx.Response:
        # Build a Request and run it through the configured handler so each
        # readiness module sees the same canned shapes.
        request = httpx.Request("GET", url)
        return handler["fn"](request)

    # Patch the two readiness modules that call httpx.get directly.
    monkeypatch.setattr(
        "dartwing_ocr.gpu_demo.readiness.ollama_reach.httpx.get", _mock_get
    )
    monkeypatch.setattr(
        "dartwing_ocr.gpu_demo.readiness.ollama_version.httpx.get", _mock_get
    )

    def _override(new_handler) -> None:
        handler["fn"] = new_handler

    return _override


# ---------------------------------------------------------------------------
# Per-test fixture folder helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def ok_fixture_folder() -> Path:
    """Path to ``tests/integration/gpu_demo/fixtures/ok/``."""
    return FIXTURES_ROOT / "ok"


# ---------------------------------------------------------------------------
# Stub PipelineComposer (T020/T022 + post-MVP IMP2)
#
# Materializes the four canonical stage 1 artifacts on disk so the orchestrator's
# full success path is exercisable without booting the real feature 003/005/008/009
# pipeline. Paired with `bypass_schema_validation` below so the post-pipeline
# readiness check 7 reports "pass" without requiring schema-perfect synthetic data.
# ---------------------------------------------------------------------------


import json as _json


def _trivial_canonical_artifacts() -> dict[str, dict]:
    """Minimal placeholder content for each canonical artifact.

    The stub composer writes these into the per-document folder. The
    `bypass_schema_validation` fixture monkeypatches check 7 to accept them.
    """
    return {
        "preprocess_output.json": {"kind": "preprocess_output", "stub": True},
        "edge_extraction_output.json": {"kind": "edge_extraction_output", "stub": True},
        "routing_decision.json": {"kind": "routing_decision", "stub": True},
        "final_structured_payload.json": {
            "kind": "final_structured_payload",
            "stub": True,
            "manual_review_required": False,
        },
    }


class _StubPipelineComposer:
    """Implements ``PipelineComposer`` Protocol for CPU-isolated tests.

    Writes synthetic artifacts into the document folder so the orchestrator's
    happy-path can complete end-to-end without composing the real pipeline.
    """

    def __init__(self, *, fail_phase: str | None = None) -> None:
        self._fail_phase = fail_phase

    def _maybe_fail(self, phase: str) -> None:
        if self._fail_phase == phase:
            raise RuntimeError(f"stub composer: forced failure at {phase}")

    def preprocess(self, document_folder, preset):  # noqa: D401, ARG002
        self._maybe_fail("preprocess")
        path = document_folder / "preprocess_output.json"
        path.write_text(
            _json.dumps(_trivial_canonical_artifacts()["preprocess_output.json"]),
            encoding="utf-8",
        )
        return path

    def extract(self, document_folder, voter_config):  # noqa: D401, ARG002
        self._maybe_fail("extraction")
        path = document_folder / "edge_extraction_output.json"
        path.write_text(
            _json.dumps(_trivial_canonical_artifacts()["edge_extraction_output.json"]),
            encoding="utf-8",
        )
        return path

    def route(self, document_folder):  # noqa: D401
        self._maybe_fail("routing")
        path = document_folder / "routing_decision.json"
        path.write_text(
            _json.dumps(_trivial_canonical_artifacts()["routing_decision.json"]),
            encoding="utf-8",
        )
        return path

    def assemble(self, document_folder):  # noqa: D401
        self._maybe_fail("final_payload")
        path = document_folder / "final_structured_payload.json"
        path.write_text(
            _json.dumps(_trivial_canonical_artifacts()["final_structured_payload.json"]),
            encoding="utf-8",
        )
        return path


@pytest.fixture
def stub_pipeline_composer():
    """Return the stub composer class so tests can instantiate it directly.

    Tests typically construct an ``OrchestratorOptions`` with
    ``composer=stub_pipeline_composer()`` and call
    ``orchestrator.run_options(options)``, OR monkey-patch the orchestrator's
    default-composer factory.
    """
    return _StubPipelineComposer


@pytest.fixture
def bypass_schema_validation(monkeypatch: pytest.MonkeyPatch):
    """Make the artifact-schema-validation readiness check always return "pass".

    The stub composer writes trivial JSON content that does not match the
    v1.3.0 schemas. Tests that exercise the orchestrator's happy-path use
    this fixture so check 7 reports pass without requiring schema-perfect
    synthetic data. (T034a / workstation smoke tests do not use this fixture
    — they exercise the real validator against real artifacts.)
    """
    from dartwing_ocr.gpu_demo.readiness import schema_validation as svm

    def _stub_validate(_path) -> None:  # noqa: D401
        return None  # always pass

    monkeypatch.setattr(svm, "_validate_artifact", _stub_validate)


@pytest.fixture
def patch_orchestrator_composer(monkeypatch: pytest.MonkeyPatch):
    """Replace the orchestrator's default composer factory with the stub.

    Returns a setter; tests call ``patch(...)`` with the stub class (or an
    instance) to install it. The setter monkey-patches
    ``_DefaultPipelineComposer`` so ``orchestrator.run(args)`` picks up the
    stub automatically without needing access to the internal
    ``OrchestratorOptions.composer`` field.
    """
    from dartwing_ocr.gpu_demo import orchestrator as orch

    def _install(composer_instance) -> None:
        # Replace the default composer constructor with one that returns the stub.
        monkeypatch.setattr(
            orch, "_DefaultPipelineComposer", lambda: composer_instance
        )

    return _install


@pytest.fixture
def force_venv_interpreter(monkeypatch: pytest.MonkeyPatch):
    """Monkeypatch ``sys.executable`` to satisfy the interpreter/venv check.

    Tests that need the readiness phase to pass without actually running from
    a Paddle ROCm venv use this fixture to force the path to look right. We
    swap the interpreter module's ``sys.executable`` AND its ``os.path.realpath``
    binding only — leaving the global ``os.path.realpath`` (used by Path.resolve)
    untouched.
    """
    fake_exe = "/workspace/.venv-paddle-rocm/bin/python"
    # Only the interpreter module sees the patched values; voter_config_loader's
    # Path.resolve() still uses the real os.path.realpath.
    monkeypatch.setattr(
        "dartwing_ocr.gpu_demo.readiness.interpreter.sys.executable", fake_exe
    )

    real_realpath = __import__("os").path.realpath

    def _patched_realpath(path, **kwargs):
        # When the interpreter check asks for sys.executable's realpath, return
        # the fake. Other callers (Path.resolve) get the real value.
        if path == fake_exe or path == "sys.executable":
            return fake_exe
        return real_realpath(path, **kwargs)

    monkeypatch.setattr(
        "dartwing_ocr.gpu_demo.readiness.interpreter.os.path.realpath",
        _patched_realpath,
    )
    return fake_exe
