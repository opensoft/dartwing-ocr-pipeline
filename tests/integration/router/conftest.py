"""Shared fixtures + helpers for router integration tests.

Tests exercise the CLI end-to-end via ``subprocess`` so exit codes, stdout
envelope, and filesystem writes are all covered.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE.parents[1] / "fixtures" / "router"


def _stage(tmp_path: Path, fixture_name: str) -> Path:
    src = FIXTURE_DIR / fixture_name
    dst = tmp_path / "edge_extraction_output.json"
    dst.write_bytes(src.read_bytes())
    return tmp_path


def _run_cli(folder: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "ledgerlinc_ocr.router", "route",
           str(folder), *extra]
    return subprocess.run(cmd, capture_output=True, text=True)


def _read_artifact(folder: Path) -> dict:
    return json.loads((folder / "routing_decision.json").read_text())


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURE_DIR


@pytest.fixture
def stage_fixture():
    return _stage


@pytest.fixture
def run_cli():
    return _run_cli


@pytest.fixture
def read_artifact():
    return _read_artifact


@pytest.fixture
def green_fixture(tmp_path: Path) -> Path:
    return _stage(tmp_path, "clean_explicit_name_full_identity.json")
