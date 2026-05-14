"""Shared pytest fixtures for the contract-test suite."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dartwing_ocr.validator.loader import ContractSet, load_contract_set

_FEATURE_TESTS_ROOT = Path(__file__).resolve().parent
_FIXTURES_ROOT = _FEATURE_TESTS_ROOT / "fixtures"
_REPO_ROOT = _FEATURE_TESTS_ROOT.parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_root() -> Path:
    return _FIXTURES_ROOT


@pytest.fixture(scope="session")
def good_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "good"


@pytest.fixture(scope="session")
def bad_fixtures_root(fixtures_root: Path) -> Path:
    return fixtures_root / "bad"


@pytest.fixture(scope="session")
def contract_set() -> ContractSet:
    return load_contract_set("1.0.0")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def load_good(good_fixtures_root: Path):
    def _load(name: str) -> dict:
        return load_json(good_fixtures_root / f"{name}.json")
    return _load


@pytest.fixture(scope="session")
def load_bad(bad_fixtures_root: Path):
    def _load(name: str) -> dict:
        return load_json(bad_fixtures_root / f"{name}.json")
    return _load
