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
US2_TWO_PAGE_PDF = FIXTURE_ROOT / "inv_020" / "source.pdf"
US2_THREE_PAGE_PDF = FIXTURE_ROOT / "inv_021" / "source.pdf"
US3_PARTIAL_PDF = FIXTURE_ROOT / "inv_030_partial_failure" / "source.pdf"
US3_BLANK_PDF = FIXTURE_ROOT / "inv_031_blank_page" / "source.pdf"
US3_ENCRYPTED_PDF = FIXTURE_ROOT / "inv_032_encrypted" / "source.pdf"
US3_MALFORMED_PDF = FIXTURE_ROOT / "inv_033_malformed" / "source.pdf"
US3_NON_PDF = FIXTURE_ROOT / "inv_034_non_pdf" / "source.pdf"
US3_ZERO_PAGE_PDF = FIXTURE_ROOT / "inv_035_zero_page" / "source.pdf"
US4_WITH_TABLE_PDF = FIXTURE_ROOT / "inv_040_with_table" / "source.pdf"
US4_NO_TABLE_PDF = FIXTURE_ROOT / "inv_041_no_table" / "source.pdf"


def _ensure_source_pdf() -> Path:
    if US1_SRC_PDF.exists():
        return US1_SRC_PDF
    sys.path.insert(0, str(FIXTURE_ROOT))
    from make_us1_single_page import build as build_us1  # type: ignore

    return build_us1()


def _ensure_us2_fixtures() -> tuple[Path, Path]:
    if US2_TWO_PAGE_PDF.exists() and US2_THREE_PAGE_PDF.exists():
        return US2_TWO_PAGE_PDF, US2_THREE_PAGE_PDF
    sys.path.insert(0, str(FIXTURE_ROOT))
    from make_us2_fixtures import build_three_page_mixed, build_two_page  # type: ignore

    return build_two_page(), build_three_page_mixed()


def _ensure_us3_fixtures() -> dict[str, Path]:
    paths = {
        "partial": US3_PARTIAL_PDF,
        "blank": US3_BLANK_PDF,
        "encrypted": US3_ENCRYPTED_PDF,
        "malformed": US3_MALFORMED_PDF,
        "non_pdf": US3_NON_PDF,
        "zero_page": US3_ZERO_PAGE_PDF,
    }
    if not all(p.exists() for p in paths.values()):
        sys.path.insert(0, str(FIXTURE_ROOT))
        from make_us3_fixtures import build_all  # type: ignore

        build_all()
    return paths


def _run_pipeline(tmp_path_factory, folder_name: str, src_pdf: Path) -> dict:
    from ledgerlinc_ocr.preprocessing import pipeline

    folder = tmp_path_factory.mktemp(folder_name) / folder_name
    folder.mkdir()
    shutil.copy(src_pdf, folder / "source.pdf")
    out = pipeline.run(pipeline.Invocation(document_folder=folder))
    with out.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    src = _ensure_source_pdf()
    return _run_pipeline(tmp_path_factory, "inv_001", src)


@pytest.fixture(scope="session")
def us2_two_page_artifact(tmp_path_factory) -> dict:
    two, _three = _ensure_us2_fixtures()
    return _run_pipeline(tmp_path_factory, "inv_020", two)


@pytest.fixture(scope="session")
def us2_three_page_artifact(tmp_path_factory) -> dict:
    _two, three = _ensure_us2_fixtures()
    return _run_pipeline(tmp_path_factory, "inv_021", three)


@pytest.fixture(scope="session")
def us3_fixtures() -> dict[str, Path]:
    return _ensure_us3_fixtures()


def _ensure_us4_fixtures() -> tuple[Path, Path]:
    if US4_WITH_TABLE_PDF.exists() and US4_NO_TABLE_PDF.exists():
        return US4_WITH_TABLE_PDF, US4_NO_TABLE_PDF
    sys.path.insert(0, str(FIXTURE_ROOT))
    from make_us4_fixtures import build_no_table, build_with_table  # type: ignore

    return build_with_table(), build_no_table()


@pytest.fixture(scope="session")
def us4_with_table_artifact(tmp_path_factory) -> dict:
    with_tbl, _ = _ensure_us4_fixtures()
    return _run_pipeline(tmp_path_factory, "inv_040", with_tbl)


@pytest.fixture(scope="session")
def us4_no_table_artifact(tmp_path_factory) -> dict:
    _, no_tbl = _ensure_us4_fixtures()
    return _run_pipeline(tmp_path_factory, "inv_041", no_tbl)


@pytest.fixture
def us3_workdir(tmp_path: Path, us3_fixtures: dict[str, Path]):
    def _stage(key: str, folder_name: str = "inv_099") -> Path:
        folder = tmp_path / folder_name
        folder.mkdir()
        shutil.copy(us3_fixtures[key], folder / "source.pdf")
        return folder

    return _stage
