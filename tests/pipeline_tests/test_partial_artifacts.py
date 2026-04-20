"""T034: partial artifacts survive on disk after processing failure."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import Runner


def test_extraction_failure_after_preprocess_wrote(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    def boom(invocation: Any, produced: dict) -> dict:
        raise RuntimeError("extraction blew up")

    folder = tmp_document_folder(1, "easy")
    code = main(
        ["run", "--document-folder", str(folder)],
        runner=Runner(extraction=boom),
    )
    assert code == 20

    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "PROCESSING_FAILURE"
    assert rec["stage"] == "extraction"
    assert rec["artifacts_written"] == [str(folder / "preprocess_output.json")]

    # file still on disk
    assert (folder / "preprocess_output.json").is_file()
    # later artifacts not written
    assert not (folder / "edge_extraction_output.json").exists()
    assert not (folder / "routing_decision.json").exists()
    assert not (folder / "final_structured_payload.json").exists()
