"""Shared fixtures for preprocessing integration tests."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE.parents[1] / "fixtures" / "preprocessing"
US1_SRC_PDF = FIXTURE_ROOT / "inv_001" / "source.pdf"


def _ensure_source_pdf() -> Path:
    if US1_SRC_PDF.exists():
        return US1_SRC_PDF
    sys.path.insert(0, str(FIXTURE_ROOT))
    from make_us1_single_page import build as build_us1  # type: ignore

    return build_us1()


@pytest.fixture(scope="session")
def us1_source_pdf() -> Path:
    return _ensure_source_pdf()


@pytest.fixture
def us1_workdir(tmp_path: Path, us1_source_pdf: Path) -> Path:
    folder = tmp_path / "inv_001"
    folder.mkdir()
    shutil.copy(us1_source_pdf, folder / "source.pdf")
    return folder


@pytest.fixture(scope="session")
def us1_artifact(tmp_path_factory) -> dict:
    """Run the pipeline once per test session and return the loaded artifact dict."""
    from ledgerlinc_ocr.preprocessing import pipeline

    src = _ensure_source_pdf()
    folder = tmp_path_factory.mktemp("us1_session") / "inv_001"
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")
    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    with out.open("r", encoding="utf-8") as f:
        return json.load(f)
