"""Unit tests for FR-020 null discipline (T068).

FR-020: missing OCR text MUST be the empty string (""), never None. The
assembled artifact dict MUST NOT contain any null values anywhere — the
frozen v1.0.0 schema pins every field to a non-null type, so a stray
None would crash schema validation and/or silently corrupt downstream
contracts.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from ledgerlinc_ocr.preprocessing import pipeline

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE.parents[1] / "fixtures" / "preprocessing"


def _ensure_us1() -> Path:
    src = FIXTURE_ROOT / "inv_001" / "source.pdf"
    if not src.exists():
        sys.path.insert(0, str(FIXTURE_ROOT))
        from make_us1_single_page import build as build_us1  # type: ignore

        return build_us1()
    return src


def _walk(obj: Any, path: str = ""):
    if obj is None:
        yield path or "<root>"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from _walk(item, f"{path}[{i}]")


def _run(tmp_path: Path) -> dict:
    src = _ensure_us1()
    folder = tmp_path / "inv_001"
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")
    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    with out.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_no_nulls_anywhere_in_assembled_artifact(tmp_path):
    artifact = _run(tmp_path)
    null_paths = list(_walk(artifact))
    assert null_paths == [], f"null values leaked into artifact at: {null_paths}"


def test_ocr_failure_yields_empty_string_not_null(tmp_path, monkeypatch):
    """When the engine crashes on a page, raw_ocr_lines must be [] (empty
    array) and any block.text must be "" (empty string), never None."""
    # V3 migration (FR-007): run_ocr_lines retired — the engine crash path is
    # now exercised via `run_page` returning `([], [], [], [warning])` per its
    # internal try/except contract.
    from ledgerlinc_ocr.preprocessing import ocr

    def _fail_engine(image, page_number, width, height):
        return [], [], [], [
            f"page {page_number}: layout extraction failed: "
            f"RuntimeError: simulated engine crash"
        ]

    monkeypatch.setattr(ocr, "run_page", _fail_engine)

    artifact = _run(tmp_path)
    page = artifact["pages"][0]
    assert page["raw_ocr_lines"] == []
    for block in page["blocks"]:
        assert block["text"] != None  # noqa: E711 — we want the literal is-not-None check
        assert isinstance(block["text"], str)
    # And still no nulls bleed into the artifact as a whole.
    assert list(_walk(artifact)) == []


def test_empty_page_still_has_empty_string_document_text(tmp_path, monkeypatch):
    """If every page comes back with zero blocks, document_text is "" not null."""
    # V3 migration (FR-007): run_ocr_lines + run_layout merged into run_page.
    from ledgerlinc_ocr.preprocessing import ocr

    def _empty_page(image, page_number, width, height):
        return [], [], [], []

    monkeypatch.setattr(ocr, "run_page", _empty_page)

    artifact = _run(tmp_path)
    assert artifact["document_text"] == ""
    assert isinstance(artifact["document_text"], str)
