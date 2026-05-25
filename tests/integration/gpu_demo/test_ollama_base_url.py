"""Phase 7 T071a: multi-Ollama disambiguation (R-023.14).

The demo MUST probe only the URL named by OLLAMA_BASE_URL; competing Ollama
instances at other URLs are not consulted (spec Edge Case).
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import httpx

from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_demo_ignores_other_ollama_urls(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """A handler that fails on any non-localhost URL still produces SUCCESS.

    The demo's monkey-patched httpx.get goes through the unified stub, which
    answers only the canonical localhost URLs. If the demo were probing other
    URLs, the stub would 404 them and readiness would fail. Successful
    --check-only proves no other URLs are probed.
    """
    competing_calls: list[str] = []

    def _strict_handler(request: httpx.Request) -> httpx.Response:
        # Only canned responses for the canonical localhost URL.
        host = request.url.host
        port = request.url.port
        if host not in ("localhost", "127.0.0.1") or port not in (None, 11434):
            competing_calls.append(str(request.url))
            return httpx.Response(404, json={"error": "wrong url"})
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
        return httpx.Response(404, json={})

    ollama_http_stub(_strict_handler)

    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.SUCCESS
    assert competing_calls == [], (
        f"demo probed non-canonical Ollama URLs: {competing_calls}"
    )

    parsed = json.loads(stdout)
    assert parsed["readiness"]["overall_passed"] is True
