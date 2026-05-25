"""US3 T045: stderr mirrors JSON diagnostic content (R-023.11).

For each readiness failure class, the stderr ERROR line and the
readiness.checks[<name>].diagnostic object surface the same observed /
expected / remediation strings.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import httpx
import pytest

from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main_capture_both(argv: list[str]) -> tuple[int, str, str]:
    from dartwing_ocr.gpu_demo.cli import main

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def test_stderr_mirrors_json_diagnostic_for_ollama_version(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.3.12"})
        return httpx.Response(200, json={"models": []})

    ollama_http_stub(handler)

    code, stdout, stderr = _invoke_main_capture_both([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.READINESS_FAILED

    parsed = json.loads(stdout)
    check = next(
        c for c in parsed["readiness"]["checks"] if c["name"] == "ollama-version"
    )
    diag = check["diagnostic"]
    assert diag is not None

    # The stderr ERROR line must contain the same observed + remediation as the JSON.
    error_lines = [ln for ln in stderr.splitlines() if ln.startswith("ERROR:")]
    assert error_lines, f"expected stderr ERROR line, got: {stderr!r}"
    combined_errors = "\n".join(error_lines)
    # Observed value in JSON should appear in stderr (modulo repr-quoting).
    assert "0.3.12" in combined_errors
    # Remediation phrase appears verbatim.
    assert diag["remediation"][:30] in combined_errors
