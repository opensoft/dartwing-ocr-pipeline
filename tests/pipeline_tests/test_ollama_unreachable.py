"""T036: simulated Ollama-unreachable at extraction stage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.runner import Runner


def test_connection_error_surfaces_cleanly(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    url = "http://localhost:11434"

    def no_ollama(invocation: Any, produced: dict) -> dict:
        raise ConnectionError(f"cannot reach {url}")

    folder = tmp_document_folder(1, "easy")
    code = main(
        ["run", "--document-folder", str(folder)],
        runner=Runner(extraction=no_ollama),
    )
    assert code == 20
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "PROCESSING_FAILURE"
    assert rec["stage"] == "extraction"
    assert url in rec["message"]
    # must not embed stack traces or module paths
    assert "Traceback" not in rec["message"]
    assert "dartwing_ocr." not in rec["message"]
