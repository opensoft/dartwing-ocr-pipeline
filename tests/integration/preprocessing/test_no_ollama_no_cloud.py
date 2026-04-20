"""FR-022 + FR-023: preprocessing is Ollama-free and cloud-free (T071).

This test runs the full US1 pipeline with outbound sockets disabled via
`pytest-socket` and `OLLAMA_BASE_URL` pointing at a deliberately
unreachable port. If preprocessing ever reaches for Ollama or any cloud
endpoint, pytest-socket will raise `SocketBlockedError` before the call
can escape the loopback device. Exit 0 + valid artifact proves the slice
is self-contained.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytest_socket")

from pytest_socket import disable_socket, enable_socket  # noqa: E402

from ledgerlinc_ocr.preprocessing import pipeline  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE.parents[1] / "fixtures" / "preprocessing"


def _ensure_us1() -> Path:
    src = FIXTURE_ROOT / "inv_001" / "source.pdf"
    if not src.exists():
        sys.path.insert(0, str(FIXTURE_ROOT))
        from make_us1_single_page import build as build_us1  # type: ignore

        return build_us1()
    return src


@pytest.fixture
def no_network():
    disable_socket()
    try:
        yield
    finally:
        enable_socket()


def test_preprocessing_runs_with_no_network_and_unreachable_ollama(
    tmp_path, monkeypatch, no_network
):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    # Belt and braces — nuke anything that might look like cloud config.
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    src = _ensure_us1()
    folder = tmp_path / "inv_001"
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")

    out = pipeline.run(pipeline.Invocation(document_folder=folder))

    assert out.exists()
    with out.open("r", encoding="utf-8") as f:
        artifact = json.load(f)

    # Schema-valid on-disk; caller will have raised long before this line
    # if any outbound socket was opened.
    assert artifact["source_type"] == "pdf"
    assert artifact["page_count"] == 1
    assert artifact["ingestion_sources"]["paddleocr_vl"]["enabled"] is True
