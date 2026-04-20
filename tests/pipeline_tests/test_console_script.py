"""T047: console script wiring (ledgerlinc-pipeline)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable

import pytest


def _console_script() -> str | None:
    return shutil.which("ledgerlinc-pipeline")


@pytest.mark.skipif(
    _console_script() is None,
    reason="ledgerlinc-pipeline console script not installed on PATH",
)
def test_console_script_matches_module_invocation(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    result = subprocess.run(
        [
            "ledgerlinc-pipeline",
            "run",
            "--document-folder",
            str(folder),
            "--overwrite",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload["document_id"] == "inv_001"
    assert payload["decision"] == "edge_accept"
