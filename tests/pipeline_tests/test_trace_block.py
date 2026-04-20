"""T028: trace block has bare filenames; no artifact contains absolute paths."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES


def _walk_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def test_trace_is_bare_filenames(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0
    final = json.loads(
        (folder / "final_structured_payload.json").read_text()
    )
    trace = final["trace"]
    for value in trace.values():
        assert "/" not in value
        assert not value.startswith("~")
        # must not be absolute
        assert not value.startswith("/")


def test_no_absolute_paths_in_any_artifact(
    tmp_document_folder: Callable[..., Path], tmp_path: Path
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0

    tmp_prefix = str(tmp_path)
    for name in RESERVED_ARTIFACT_NAMES:
        payload = json.loads((folder / name).read_text())
        for s in _walk_strings(payload):
            assert not s.startswith("/"), f"{name}: absolute path leaked: {s}"
            assert not s.startswith("~"), f"{name}: home-relative path: {s}"
            assert tmp_prefix not in s, f"{name}: tmp_path leaked: {s}"
