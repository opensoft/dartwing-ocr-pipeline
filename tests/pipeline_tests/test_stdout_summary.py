"""T015: stdout summary shape."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def test_stdout_is_single_json_line(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line]
    assert len(lines) == 1, f"expected 1 line, got {len(lines)}"
    payload = json.loads(lines[0])
    assert set(payload.keys()) == {
        "document_id",
        "decision",
        "manual_review_required",
        "review_reason",
        "artifacts",
    }
    assert payload["document_id"] == "inv_001"
    assert payload["decision"] == "edge_accept"
    assert payload["manual_review_required"] is False
    assert payload["review_reason"] is None
    assert set(payload["artifacts"].keys()) == set(RESERVED_ARTIFACT_NAMES)
    for name, path in payload["artifacts"].items():
        assert path == str(folder / name)


def test_stdout_matches_routing_decision_on_disk(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(3, "hard")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip())

    routing = json.loads((folder / "routing_decision.json").read_text())
    assert payload["decision"] == routing["decision"]
    assert (
        payload["manual_review_required"]
        == routing["review_status"]["manual_review_required"]
    )
    assert (
        payload["review_reason"] == routing["review_status"]["review_reason"]
    )
