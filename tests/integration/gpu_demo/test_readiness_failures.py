"""US2 T040: each readiness failure class produces the right closed-vocab diagnostic.

Parameterized across the 6 infrastructure-readiness check classes. Asserts:
- exit 1 (READINESS_FAILED)
- runtime_outcome is null
- failure_kind == "readiness-failed"
- failing_check_name matches the broken class
- diagnostic has the closed-vocab shape (checked/observed/expected/remediation)
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import httpx
import pytest

from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def _ollama_unreachable(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Connection refused", request=request)


def _ollama_old_version(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.3.12"})
    return httpx.Response(200, json={"models": []})


def _ollama_partial_placement(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.4.5"})
    return httpx.Response(
        200,
        json={"models": [{"name": "qwen2.5-vl:7b", "size": 4906000000, "size_vram": 0}]},
    )


def _ollama_ctx_too_small(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.4.5"})
    return httpx.Response(
        200,
        json={
            "models": [
                {
                    "name": "qwen2.5-vl:7b",
                    "size": 4906000000,
                    "size_vram": 4906000000,
                    "context_length": 512,
                }
            ]
        },
    )


@pytest.mark.parametrize(
    "case_id, installer, expected_check",
    [
        ("paddle_cpu_only", "paddle", "paddle-rocm-preflight"),
        ("ollama_unreachable", _ollama_unreachable, "ollama-reachability"),
        ("ollama_old_version", _ollama_old_version, "ollama-version"),
        ("ollama_partial_placement", _ollama_partial_placement, "ollama-model-gpu-placement"),
        ("ollama_ctx_too_small", _ollama_ctx_too_small, "ollama-context-length"),
    ],
)
def test_readiness_failure_class(
    case_id,
    installer,
    expected_check,
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    if installer == "paddle":
        from dartwing_ocr.preprocessing.preflight import PreflightState

        paddle_preflight_stub(PreflightState.PADDLE_CPU_ONLY, "Switch to GPU build")
    else:
        ollama_http_stub(installer)

    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.READINESS_FAILED, f"case {case_id} expected READINESS_FAILED"

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] is None
    assert parsed["failure_kind"] == "readiness-failed"
    assert parsed["failing_check_name"] == expected_check, (
        f"case {case_id} expected failing_check={expected_check}, got {parsed['failing_check_name']}"
    )

    # The failing check's diagnostic has the closed-vocab shape.
    failing_check = next(
        c for c in parsed["readiness"]["checks"] if c["name"] == expected_check
    )
    diag = failing_check["diagnostic"]
    assert diag is not None
    for key in ("checked", "observed", "expected", "remediation"):
        assert key in diag, f"case {case_id} diagnostic missing key {key}: {diag}"
    assert isinstance(diag["remediation"], str)
    assert len(diag["remediation"]) > 0


def test_interpreter_venv_failure_class(
    paddle_preflight_stub,
    ollama_http_stub,
    monkeypatch,
    ok_fixture_folder: Path,
) -> None:
    """interpreter/venv check fails when sys.executable is not in expected venv.

    Patches ONLY the interpreter module's view of sys.executable + the
    interpreter-local helper, so voter_config_loader's Path.resolve() (which
    uses the global os.path.realpath) stays functional. The lambda discriminates
    by input path to avoid the broadcast-monkey-patch bug.
    """
    fake_exe = "/usr/bin/python3"  # NOT in .venv-paddle-rocm
    monkeypatch.setattr(
        "dartwing_ocr.gpu_demo.readiness.interpreter.sys.executable", fake_exe
    )

    import os as _os

    real_realpath = _os.path.realpath

    def _scoped_realpath(path, **kwargs):
        # Only return the fake_exe when asked about sys.executable itself.
        if str(path) == fake_exe:
            return fake_exe
        return real_realpath(path, **kwargs)

    monkeypatch.setattr(
        "dartwing_ocr.gpu_demo.readiness.interpreter.os.path.realpath",
        _scoped_realpath,
    )

    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.READINESS_FAILED

    parsed = json.loads(stdout)
    assert parsed["failing_check_name"] == "interpreter/venv"
    assert parsed["failure_kind"] == "readiness-failed"
