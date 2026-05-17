"""Shared fixtures for pipeline contract tests."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
    b"xref\n0 3\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000053 00000 n \n"
    b"trailer<</Size 3/Root 1 0 R>>\n"
    b"startxref\n100\n%%EOF\n"
)


@pytest.fixture
def tmp_pdf_bytes() -> bytes:
    return MINIMAL_PDF_BYTES


@pytest.fixture(autouse=True)
def offline_stage_registry_for_unit_tests():
    """Keep pipeline unit tests on explicit offline stage fallbacks."""
    from dartwing_ocr.pipeline import stages as stages_mod

    stages_mod.reset_live_registry(stub_fallback_only=True)
    yield
    stages_mod.reset_live_registry()


@pytest.fixture
def tmp_pdf_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    p.write_bytes(MINIMAL_PDF_BYTES)
    return p


@pytest.fixture
def tmp_document_folder(tmp_path: Path) -> Callable[[int, str], Path]:
    def _make(nnn: int = 1, difficulty: str = "easy") -> Path:
        folder = tmp_path / f"inv_{nnn:03d}_{difficulty}"
        folder.mkdir()
        (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
        return folder

    return _make


@pytest.fixture
def tmp_corpus_root(tmp_path: Path) -> Callable[[int], Path]:
    def _make(n: int = 20) -> Path:
        root = tmp_path / "corpus"
        root.mkdir()
        difficulties = ["easy", "medium", "hard", "missing_name"]
        for i in range(n):
            diff = difficulties[i % len(difficulties)]
            folder = root / f"inv_{i + 1:03d}_{diff}"
            folder.mkdir()
            (folder / "source.pdf").write_bytes(MINIMAL_PDF_BYTES)
        return root

    return _make
