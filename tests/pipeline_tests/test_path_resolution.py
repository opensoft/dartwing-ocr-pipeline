"""T007: path resolution and document-id derivation."""
from __future__ import annotations

from pathlib import Path

import pytest

from ledgerlinc_ocr.pipeline.path_resolution import (
    PathResolutionError,
    derive_document_id,
    resolve_destination,
    resolve_input_pdf,
)


def test_document_folder_resolves_source_pdf(tmp_path: Path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    pdf = resolve_input_pdf(None, folder)
    assert pdf == (folder / "source.pdf").resolve()


def test_input_is_passed_through(tmp_path: Path):
    p = tmp_path / "some.pdf"
    p.write_bytes(b"%PDF-1.4\n")
    assert resolve_input_pdf(p, None) == p.resolve()


def test_mutual_exclusion_raises(tmp_path: Path):
    with pytest.raises(PathResolutionError):
        resolve_input_pdf(tmp_path / "a.pdf", tmp_path)


def test_neither_raises():
    with pytest.raises(PathResolutionError):
        resolve_input_pdf(None, None)


def test_dest_defaults_to_document_folder(tmp_path: Path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    assert resolve_destination(None, folder, None) == folder.resolve()


def test_dest_defaults_to_input_parent(tmp_path: Path):
    p = tmp_path / "some.pdf"
    p.write_bytes(b"x")
    assert resolve_destination(p, None, None) == tmp_path.resolve()


def test_dest_output_dir_overrides(tmp_path: Path):
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    other = tmp_path / "elsewhere"
    other.mkdir()
    assert resolve_destination(None, folder, other) == other.resolve()


@pytest.mark.parametrize(
    "folder_name,expected",
    [
        ("inv_001_easy", "inv_001"),
        ("inv_042_medium", "inv_042"),
        ("inv_007_hard", "inv_007"),
        ("inv_999_missing_name", "inv_999"),
    ],
)
def test_derive_document_id_matches(folder_name: str, expected: str):
    assert derive_document_id(folder_name) == expected


@pytest.mark.parametrize(
    "folder_name",
    [
        "invoice_001",
        "inv_1_easy",
        "inv_001_unknown",
        "inv_001",
        "",
        "some_random_name",
    ],
)
def test_derive_document_id_returns_none_for_non_matches(folder_name: str):
    assert derive_document_id(folder_name) is None
