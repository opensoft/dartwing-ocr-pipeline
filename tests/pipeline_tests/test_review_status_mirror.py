"""T025: review_status mirrored between routing and final_payload."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from dartwing_ocr.pipeline.cli import main


def test_review_status_matches_byte_for_byte(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    routing = json.loads((folder / "routing_decision.json").read_text())
    final = json.loads(
        (folder / "final_structured_payload.json").read_text()
    )
    assert (
        routing["review_status"]["manual_review_required"]
        == final["review_status"]["manual_review_required"]
    )
    assert (
        routing["review_status"]["review_reason"]
        == final["review_status"]["review_reason"]
    )
