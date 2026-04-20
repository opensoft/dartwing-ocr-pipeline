"""T035: each stage failure labels stage and accumulates artifacts correctly."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import Runner


def _boom(stage_name: str):
    def _stub(invocation: Any, produced: dict) -> dict:
        raise RuntimeError(f"{stage_name} failed")

    return _stub


@pytest.mark.parametrize(
    "stage_name,expected_count",
    [
        ("preprocess", 0),
        ("extraction", 1),
        ("routing", 2),
        ("final_payload", 3),
    ],
)
def test_stage_failure_labels(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
    stage_name: str,
    expected_count: int,
):
    folder = tmp_document_folder(1, "easy")
    kwargs: dict[str, Any] = {stage_name: _boom(stage_name)}
    runner = Runner(**kwargs)
    code = main(
        ["run", "--document-folder", str(folder), "--overwrite"],
        runner=runner,
    )
    assert code == 20
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["stage"] == stage_name
    assert len(rec["artifacts_written"]) == expected_count
