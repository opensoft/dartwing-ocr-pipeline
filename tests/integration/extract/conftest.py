"""Shared fixtures for US1-US5 integration tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures" / "extract"


@pytest.fixture
def us1_happy_folder(tmp_path: Path) -> Path:
    """Copy the US1 happy fixture into a tmp folder and return its path.

    The copy keeps the voter_config.yaml + prompt + voter_response fixture
    together so path resolution within the test mirrors the on-disk layout
    a real operator would see.
    """

    src = _FIXTURE_ROOT / "us1_happy"
    dest = tmp_path / "us1_happy"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def us2_evidence_folder(tmp_path: Path) -> Path:
    """Copy the US2 bogus-evidence fixture into a tmp folder."""

    src = _FIXTURE_ROOT / "us2_evidence"
    dest = tmp_path / "us2_evidence"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def us4_qwen_sim_folder(tmp_path: Path) -> Path:
    src = _FIXTURE_ROOT / "us4_qwen_sim"
    dest = tmp_path / "us4_qwen_sim"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def us3_missing_name_folder(tmp_path: Path) -> Path:
    src = _FIXTURE_ROOT / "us3_missing_name"
    dest = tmp_path / "us3_missing_name"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def us3_grounded_name_folder(tmp_path: Path) -> Path:
    src = _FIXTURE_ROOT / "us3_grounded_name"
    dest = tmp_path / "us3_grounded_name"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def us5_failure_folder(tmp_path: Path):
    """Factory: copies `tests/fixtures/extract/us5_failures/<name>/` into tmp."""

    def _copy(name: str) -> Path:
        src = _FIXTURE_ROOT / "us5_failures" / name
        dest = tmp_path / name
        shutil.copytree(src, dest)
        return dest

    return _copy


@pytest.fixture
def us5_partial_input_folder(tmp_path: Path) -> Path:
    src = _FIXTURE_ROOT / "us5_partial_input"
    dest = tmp_path / "us5_partial_input"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def run_extractor():
    """Returns a callable that invokes `dartwing_ocr.extract.cli.main` in-process."""

    def _run(folder: Path, voter_config: Path, voter: str = "stub") -> int:
        from dartwing_ocr.extract.cli import main as extract_main

        return extract_main(
            [
                "--folder",
                str(folder),
                "--voter",
                voter,
                "--voter-config",
                str(voter_config),
            ]
        )

    return _run


@pytest.fixture
def load_output():
    def _load(folder: Path) -> dict:
        return json.loads((folder / "edge_extraction_output.json").read_text(encoding="utf-8"))

    return _load
