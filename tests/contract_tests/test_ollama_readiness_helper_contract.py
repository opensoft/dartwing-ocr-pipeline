"""Feature 021 / T008: CPU-safe contract test for the Ollama readiness helper.

Exercises every exit-code path of ``scripts/check-ollama-gpu-readiness.sh``
(see ``specs/021-gpu-mvp-promotion/contracts/ollama-readiness-helper.md``)
against an ephemeral stdlib ``http.server`` that serves the appropriate
``/api/ps`` fixture JSON.

No GPU required. No new pytest dependency. Runs under ``pytest -m 'not gpu'``.
"""

from __future__ import annotations

import json
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts" / "check-ollama-gpu-readiness.sh"
FIXTURES_DIR = REPO_ROOT / "tests" / "contract_tests" / "fixtures"

# The pass / partial / cpu_only fixtures all load this model name. Must
# match `configs/voter/ollama-gpu.yaml` `model_name`, which is pinned to
# what the `ollama@gpu` extraction profile binds (gemma-edge.yaml ollama.model_tag).
MODEL_LOADED = "gemma4:e4b"
# The missing fixture loads `gemma2:9b` instead; querying MODEL_LOADED returns
# "not loaded" because the matched-name lookup fails.


def _make_handler(fixture_bytes: bytes):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/api/ps":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(fixture_bytes)))
                self.end_headers()
                self.wfile.write(fixture_bytes)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args, **kwargs):  # noqa: A003
            # Silence the default request-logging on stderr; tests assert against
            # the helper's stderr, not the server's.
            return

    return Handler


@pytest.fixture
def serve_fixture():
    """Yield a context-manager factory that serves a fixture at /api/ps.

    Usage::

        with serve_fixture("ollama_api_ps_pass.json") as url:
            # call helper with --base-url url
    """

    @contextmanager
    def _serve(fixture_name: str):
        path = FIXTURES_DIR / fixture_name
        assert path.exists(), f"fixture not found: {path}"
        body = path.read_bytes()
        handler = _make_handler(body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://{host}:{port}"
        finally:
            server.shutdown()
            server.server_close()
            # Multi-agent-review LOW-7 fix: 2s join can flake on slow CI runners
            # under load (the serve_forever loop sometimes takes >2s to notice the
            # shutdown flag and unwind). 5s is a generous upper bound that still
            # surfaces a stuck-thread bug fast in local runs.
            thread.join(timeout=5)

    return _serve


def _write_voter_config(tmp_path: Path, model_name: str | None) -> Path:
    path = tmp_path / "voter.yaml"
    if model_name is None:
        path.write_text("other_key: value\n")
    else:
        path.write_text(f'model_name: "{model_name}"\n')
    return path


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HELPER), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


# ---------------------------------------------------------------------------
# Exit 0 — PASS
# ---------------------------------------------------------------------------


def test_pass_when_model_fully_on_gpu(tmp_path, serve_fixture):
    voter_config = _write_voter_config(tmp_path, MODEL_LOADED)
    with serve_fixture("ollama_api_ps_pass.json") as url:
        result = _run_helper("--voter-config", str(voter_config), "--base-url", url)

    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}; stderr={result.stderr!r}"
    )
    assert result.stderr == ""
    parsed = json.loads(result.stdout.strip())
    assert parsed["status"] == "pass"
    assert parsed["model_name"] == MODEL_LOADED
    assert parsed["size"] == parsed["size_vram"] > 0
    assert parsed["base_url"] == url
    assert parsed["voter_config_path"] == str(voter_config)
    assert "timestamp_utc" in parsed


# ---------------------------------------------------------------------------
# Exit 1 — partial GPU (covers both 0 < size_vram < size and size_vram == 0)
# ---------------------------------------------------------------------------


def test_fail_partial_gpu(tmp_path, serve_fixture):
    voter_config = _write_voter_config(tmp_path, MODEL_LOADED)
    with serve_fixture("ollama_api_ps_partial.json") as url:
        result = _run_helper("--voter-config", str(voter_config), "--base-url", url)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "partially on GPU" in result.stderr
    assert MODEL_LOADED in result.stderr
    assert "size_vram=" in result.stderr
    assert "size=" in result.stderr


def test_fail_cpu_only(tmp_path, serve_fixture):
    """``size_vram == 0`` is the CPU-only sub-case of exit 1."""
    voter_config = _write_voter_config(tmp_path, MODEL_LOADED)
    with serve_fixture("ollama_api_ps_cpu_only.json") as url:
        result = _run_helper("--voter-config", str(voter_config), "--base-url", url)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "partially on GPU" in result.stderr
    assert "size_vram=0" in result.stderr


# ---------------------------------------------------------------------------
# Exit 2 — model not loaded
# ---------------------------------------------------------------------------


def test_fail_not_loaded(tmp_path, serve_fixture):
    voter_config = _write_voter_config(tmp_path, MODEL_LOADED)
    with serve_fixture("ollama_api_ps_missing.json") as url:
        result = _run_helper("--voter-config", str(voter_config), "--base-url", url)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "not loaded" in result.stderr
    assert MODEL_LOADED in result.stderr


# ---------------------------------------------------------------------------
# Exit 3 — Ollama unreachable
# ---------------------------------------------------------------------------


def test_fail_unreachable_server_down(tmp_path):
    """Server never started; curl fails to connect."""
    voter_config = _write_voter_config(tmp_path, MODEL_LOADED)
    # Port 1 is the IANA reserved tcpmux port; curl will fail to connect.
    result = _run_helper(
        "--voter-config",
        str(voter_config),
        "--base-url",
        "http://127.0.0.1:1",
    )

    assert result.returncode == 3
    assert result.stdout == ""
    assert "Ollama unreachable" in result.stderr


# ---------------------------------------------------------------------------
# Exit 4 — voter-config malformed / missing
# ---------------------------------------------------------------------------


def test_fail_config_file_missing(tmp_path):
    result = _run_helper(
        "--voter-config",
        str(tmp_path / "nonexistent.yaml"),
    )

    assert result.returncode == 4
    assert result.stdout == ""
    assert "missing or malformed" in result.stderr
    assert "file not found" in result.stderr


def test_fail_config_no_model_name_key(tmp_path):
    voter_config = _write_voter_config(tmp_path, model_name=None)
    result = _run_helper("--voter-config", str(voter_config))

    assert result.returncode == 4
    assert result.stdout == ""
    assert "missing or malformed" in result.stderr
    assert "no model_name" in result.stderr


def test_fail_no_voter_config_flag():
    result = _run_helper()

    assert result.returncode == 4
    assert result.stdout == ""
    assert "--voter-config" in result.stderr
    assert "missing or malformed" in result.stderr


# Regression tests for the multi-agent-review HIGH-1 bug
# (commit ${HEAD} 2026-05-19): truncated flag (last argv with no value
# following) used to drive an infinite loop because `shift 2 || true`
# masked `shift`'s failure when only 1 positional remained. Now exits 4
# with a named-prerequisite stderr template per FR-004 / SC-002.


def test_fail_voter_config_flag_truncated(tmp_path):
    """`--voter-config` as the last argv with no value following MUST exit 4
    fast (HIGH-1 regression) — not hang in an infinite loop."""
    result = _run_helper("--voter-config")

    assert result.returncode == 4
    assert result.stdout == ""
    assert "missing or malformed" in result.stderr
    assert "--voter-config requires a value" in result.stderr


def test_fail_base_url_flag_truncated(tmp_path):
    """`--base-url` as the last argv with no value following MUST exit 4
    fast (HIGH-1 regression)."""
    voter_config = _write_voter_config(tmp_path, MODEL_LOADED)
    result = _run_helper("--voter-config", str(voter_config), "--base-url")

    assert result.returncode == 4
    assert result.stdout == ""
    assert "missing or malformed" in result.stderr
    assert "--base-url requires a value" in result.stderr
