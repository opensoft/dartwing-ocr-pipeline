"""Shared fixtures for evidence-packet integration tests."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "evidence_packet"


@pytest.fixture
def folder_with_preprocess(tmp_path: Path):
    """Return a callable that materialises ``tmp_path/inv_001_easy/preprocess_output.json``.

    Usage:

        def test_x(folder_with_preprocess):
            folder = folder_with_preprocess("minimal_valid.json")
            # folder/preprocess_output.json exists
    """

    def _make(fixture_name: str) -> Path:
        src = _FIXTURE_ROOT / fixture_name
        folder = tmp_path / "inv_001_easy"
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, folder / "preprocess_output.json")
        return folder

    return _make
