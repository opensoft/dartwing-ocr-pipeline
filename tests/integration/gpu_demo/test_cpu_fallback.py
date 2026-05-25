"""US4 T058/T059: post-run CPU-fallback detection tests (R-023.15).

T058: post-run /api/ps shows size_vram == 0 → outcome rewritten to
       failed_at_extraction with failure_kind = cpu-fallback-detected (exit 4).
T059: post-run probe unreachable → success kept but failure_kind set to
       post-run-interrogation-unreachable.
"""

from __future__ import annotations

import io
import itertools
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


@pytest.fixture
def per_doc(tmp_path: Path) -> Path:
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)
    return folder


def test_post_run_probe_detects_ollama_fallback(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    monkeypatch,
    per_doc: Path,
) -> None:
    """Pre-run = GPU-placed; post-run = size_vram=0 → cpu-fallback-detected."""
    # Counter to alternate between pre-run and post-run /api/ps responses.
    call_count = {"count": 0}

    def _switching_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.4.5"})
        if request.url.path == "/api/ps":
            call_count["count"] += 1
            if call_count["count"] == 1:
                # Readiness phase: fully GPU-placed.
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
            # Post-run interrogation: size_vram dropped to 0 (CPU fallback).
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

    ollama_http_stub(_switching_handler)
    # Stub Paddle post-run to also report success so only Ollama triggers fallback.
    from dartwing_ocr.gpu_demo import cpu_fallback as cpu_fb_mod

    def _stub_paddle_post():
        return "consistent"

    monkeypatch.setattr(cpu_fb_mod, "_probe_paddle_post_run", _stub_paddle_post)

    # Make the cpu_fallback module's httpx.get use the same mock.
    monkeypatch.setattr(
        cpu_fb_mod.httpx, "get",
        lambda url, **kwargs: _switching_handler(httpx.Request("GET", url))
    )

    patch_orchestrator_composer(stub_pipeline_composer())
    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])

    assert code == ExitCode.PIPELINE_RUNTIME_ERROR == 4

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "failed_at_extraction"
    assert parsed["failure_kind"] == "cpu-fallback-detected"
    cpu = parsed["cpu_fallback_detection"]
    assert cpu["ollama_post_run"] == "fell_back"


def test_post_run_probe_unreachable_keeps_success(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    monkeypatch,
    per_doc: Path,
) -> None:
    """Pre-run = GPU-placed; post-run probe times out → success + failure_kind set."""
    call_count = {"count": 0}

    def _flaky_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.4.5"})
        if request.url.path == "/api/ps":
            call_count["count"] += 1
            if call_count["count"] == 1:
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
            raise httpx.ConnectTimeout("post-run probe timed out", request=request)
        return httpx.Response(404, json={})

    ollama_http_stub(_flaky_handler)
    from dartwing_ocr.gpu_demo import cpu_fallback as cpu_fb_mod

    monkeypatch.setattr(
        cpu_fb_mod.httpx, "get",
        lambda url, **kwargs: _flaky_handler(httpx.Request("GET", url))
    )

    def _stub_paddle_post():
        return "consistent"

    monkeypatch.setattr(cpu_fb_mod, "_probe_paddle_post_run", _stub_paddle_post)

    patch_orchestrator_composer(stub_pipeline_composer())
    code, stdout = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])

    # Success outcome retained (probe unreachable doesn't drop us out).
    assert code == ExitCode.SUCCESS == 0

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "success"
    assert parsed["failure_kind"] == "post-run-interrogation-unreachable"
    cpu = parsed["cpu_fallback_detection"]
    assert cpu["ollama_post_run"] == "unreachable"
