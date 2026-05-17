"""T043: path_resolution functions are pure (no env, no time, no FS mutation)."""
from __future__ import annotations

from pathlib import Path

import pytest

from dartwing_ocr.pipeline import path_resolution
from dartwing_ocr.pipeline.path_resolution import (
    derive_document_id,
    resolve_destination,
    resolve_input_pdf,
)


def test_derive_idempotent_under_env_changes(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://somewhere:1")
    a = derive_document_id("inv_001_easy")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    b = derive_document_id("inv_001_easy")
    assert a == b == "inv_001"


def test_resolve_input_pdf_pure(tmp_path: Path):
    folder = tmp_path / "inv_007_hard"
    folder.mkdir()
    first = resolve_input_pdf(None, folder)
    second = resolve_input_pdf(None, folder)
    assert first == second
    # No side effects — source.pdf was not created by the function
    assert not (folder / "source.pdf").exists()


def test_resolve_destination_pure(tmp_path: Path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    a = resolve_destination(None, folder, None)
    b = resolve_destination(None, folder, None)
    assert a == b


def test_module_has_no_time_or_env_imports():
    src = Path(path_resolution.__file__).read_text()
    assert "os.environ" not in src
    assert "time.time" not in src
    assert "datetime" not in src
