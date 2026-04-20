"""T006: PDF magic byte check contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.pdf_check import is_pdf


def test_valid_pdf_prefix(tmp_path: Path, tmp_pdf_bytes: bytes):
    p = tmp_path / "x.pdf"
    p.write_bytes(tmp_pdf_bytes)
    assert is_pdf(p) is True


def test_four_byte_file(tmp_path: Path):
    p = tmp_path / "short.pdf"
    p.write_bytes(b"%PDF")
    assert is_pdf(p) is False


def test_empty_file(tmp_path: Path):
    p = tmp_path / "empty.pdf"
    p.write_bytes(b"")
    assert is_pdf(p) is False


def test_non_pdf_bytes(tmp_path: Path):
    p = tmp_path / "nope.pdf"
    p.write_bytes(b"Hello, world!\n")
    assert is_pdf(p) is False


def test_non_existent_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        is_pdf(tmp_path / "missing.pdf")
