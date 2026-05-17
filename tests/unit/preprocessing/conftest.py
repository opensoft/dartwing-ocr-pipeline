"""Shared fixtures for ``tests/unit/preprocessing/`` feature 020
CPU-safe regression tests.

Centralized per Sourcery PR #42 review: both
``test_cpu_warn_and_proceed_evidence_gate.py`` and
``test_evidence_gate_no_warn_paths.py`` previously defined identical
copies of ``tmp_inv_folder`` and the minimal-artifact pipeline mock.
Future changes to the minimal artifact shape (e.g., contract-set
bumps) now only need to land here.

The pipeline mock is exposed as a factory fixture
(``mock_pipeline_run_minimal_artifact``) instead of a free function so
test files can rely on it without `from .conftest import …` (which
fails under pytest's ``--import-mode=importlib`` setting with no
``__init__.py`` in this directory).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_inv_folder(tmp_path: Path) -> Path:
    """Provide a writable folder with a copied real ``source.pdf`` so the
    CLI's input-validation passes without modifying the committed corpus
    baseline (FR-019 / SC-007). Mirrors test_cpu_warn_and_proceed.py."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    repo_root = Path(__file__).resolve().parents[3]
    source = (
        repo_root
        / "tests"
        / "stage1_vendor_identity"
        / "inv_001_easy"
        / "source.pdf"
    )
    shutil.copy(source, folder / "source.pdf")
    return folder


@pytest.fixture
def mock_pipeline_run_minimal_artifact() -> Callable[[Path], MagicMock]:
    """Factory fixture that builds a mock of
    ``preprocessing.pipeline.run`` returning a minimal artifact shape
    suitable for the CLI's post-run JSON read + run_summary emission.

    The empty ``pages`` list deliberately steers the evidence gate to
    the ``insufficient`` boundary case (per spec §Edge Cases) so test
    assertions remain stable regardless of OCR output drift.
    """

    def _build(folder: Path) -> MagicMock:
        artifact_path = folder / "preprocess_output.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "document_id": folder.name,
                    "warnings": [],
                    "pages": [],
                }
            )
        )
        return MagicMock(return_value=artifact_path)

    return _build
