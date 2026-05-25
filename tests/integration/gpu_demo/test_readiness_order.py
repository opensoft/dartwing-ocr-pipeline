"""US2 T039: fixed-order readiness execution + skip-on-upstream-fail.

For each of checks 1–6 being the first to fail, asserts:
- Checks before the failing one are ``"pass"``
- The failing check has status ``"fail"``
- Every check AFTER the failing one is ``"skipped"`` (FR-026)
- ``failing_check_name`` is the first failing check (FR-016 expanded)
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


def _connection_error_handler(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Connection refused", request=request)


def _old_version_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.3.12"})
    if request.url.path == "/api/ps":
        return httpx.Response(
            200, json={"models": [{"name": "qwen2.5-vl:7b", "size": 1, "size_vram": 1}]}
        )
    return httpx.Response(404, json={})


def _partial_placement_handler(request: httpx.Request) -> httpx.Response:
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
                        "size_vram": 0,
                    }
                ]
            },
        )
    return httpx.Response(404, json={})


def _ctx_len_too_small_handler(request: httpx.Request) -> httpx.Response:
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
                        "context_length": 1024,
                    }
                ]
            },
        )
    return httpx.Response(404, json={})


@pytest.mark.parametrize(
    "failing_check, install_handler",
    [
        # interpreter/venv tested separately (we'd need to undo force_venv_interpreter)
        ("paddle-rocm-preflight", None),  # set via paddle_preflight_stub setter
        ("ollama-reachability", _connection_error_handler),
        ("ollama-version", _old_version_handler),
        ("ollama-model-gpu-placement", _partial_placement_handler),
        ("ollama-context-length", _ctx_len_too_small_handler),
    ],
)
def test_skip_on_upstream_fail(
    failing_check: str,
    install_handler,
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """When check N fails, checks 1..N-1 pass and N+1..6 are skipped."""
    if failing_check == "paddle-rocm-preflight":
        from dartwing_ocr.preprocessing.preflight import PreflightState

        paddle_preflight_stub(PreflightState.PADDLE_CPU_ONLY, "Switch to GPU build")
    elif install_handler is not None:
        ollama_http_stub(install_handler)

    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.READINESS_FAILED

    parsed = json.loads(stdout)
    assert parsed["failing_check_name"] == failing_check
    assert parsed["failure_kind"] == "readiness-failed"

    statuses = {c["name"]: c["status"] for c in parsed["readiness"]["checks"]}

    # Find the position of the failing check in the fixed order.
    order = [
        "interpreter/venv", "paddle-rocm-preflight", "ollama-reachability",
        "ollama-version", "ollama-model-gpu-placement", "ollama-context-length",
        "artifact-schema-validation", "pipeline-runtime-timeout",
    ]
    fail_idx = order.index(failing_check)

    for i, name in enumerate(order):
        if i < fail_idx:
            assert statuses[name] == "pass", f"expected {name} pass; got {statuses[name]}"
        elif i == fail_idx:
            assert statuses[name] == "fail"
        else:
            assert statuses[name] == "skipped", f"expected {name} skipped; got {statuses[name]}"
