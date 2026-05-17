"""T027: corpus idempotency — two runs with --overwrite leave only the 4 reserved artifacts."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_two_runs_with_overwrite_are_idempotent(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    source = folder / "source.pdf"
    (folder / "expected.json").write_text('{"vendor_candidate":{}}', encoding="utf-8")
    (folder / "notes.md").write_text("keep", encoding="utf-8")

    before = _sha256(source)

    for _ in range(2):
        code = main(["run", "--document-folder", str(folder), "--overwrite"])
        assert code == 0

    after = _sha256(source)
    assert before == after

    files = {p.name for p in folder.iterdir() if p.is_file()}
    expected_files = set(RESERVED_ARTIFACT_NAMES) | {
        "source.pdf",
        "expected.json",
        "notes.md",
    }
    assert files == expected_files
    # No stray subdirs
    assert [p for p in folder.iterdir() if p.is_dir()] == []
