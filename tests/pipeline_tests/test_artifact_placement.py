"""T014: exactly four artifacts placed, no siblings touched."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def test_exactly_four_reserved_artifacts(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    actual = {p.name for p in folder.iterdir() if p.is_file()}
    assert set(RESERVED_ARTIFACT_NAMES) <= actual
    # no temp or backup sibling files
    assert not any(
        n.startswith(".") or n.endswith(".tmp") or n.endswith("~")
        for n in actual
    )
    # no subfolders
    subdirs = [p for p in folder.iterdir() if p.is_dir()]
    assert subdirs == []


def test_preexisting_nonreserved_files_untouched(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(2, "medium")
    expected = folder / "expected.json"
    notes = folder / "notes.md"
    expected.write_text('{"x":1}', encoding="utf-8")
    notes.write_text("hello", encoding="utf-8")
    expected_mtime = expected.stat().st_mtime_ns
    notes_bytes = notes.read_bytes()

    code = main(["run", "--document-folder", str(folder)])
    assert code == 0

    assert expected.stat().st_mtime_ns == expected_mtime
    assert notes.read_bytes() == notes_bytes
    # Reserved artifacts are present
    for name in RESERVED_ARTIFACT_NAMES:
        assert (folder / name).is_file()
