"""Shared corpus-fixture builders for US5 calibration-handling tests.

Extracted per Sonar duplication finding on PR #50 (2026-05-24): the
``_seed_folder`` + ``_write_sidecar`` helpers were replicated identically
across two test files (``test_us5_calibration_handling.py`` and
``test_validate_corpus_calibration_reporting.py``), pushing
duplicated-lines density to 4.2% (Sonar threshold 3%).

These helpers copy the canonical ``inv_001_easy`` good fixture to an
arbitrary basename (so calibration-style names like
``inv_024_hard_degraded_body`` can be staged for testing) and rewrite
the per-folder ``expected.json`` so the folder validator accepts the
fixture regardless of basename.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

# Canonical good-fixture location shared by both test files
# (tests/contract_tests/fixtures/good/ — the same source both files
# previously referenced via their own per-file GOOD_FIXTURE_FOLDER
# constants before this dedupe).
GOOD_FIXTURE_FOLDER = (
    Path(__file__).resolve().parents[1]
    / "contract_tests"
    / "fixtures"
    / "good"
    / "folders"
    / "inv_001_easy"
)


def seed_corpus_folder(target_root: Path, folder_name: str) -> Path:
    """Copy the canonical ``inv_001_easy`` good fixture under
    ``target_root`` with the requested basename and rewrite its
    ``expected.json`` so the per-folder validator accepts it regardless
    of basename (including calibration-style basenames like
    ``inv_024_hard_degraded_body``).

    Picks a ``difficulty`` value the folder schema accepts based on the
    basename suffix:
    * ``_easy`` → ``easy``
    * ``_medium`` → ``medium``
    * ``_missing_name`` → ``missing_name``
    * everything else (including calibration suffixes) → ``hard``

    ``notes.md`` is required by the folder schema for ``hard`` and
    ``missing_name`` difficulties. The seed fixture already ships one,
    so no extra write is needed here.

    Returns the path to the newly-staged folder.
    """
    target = target_root / folder_name
    shutil.copytree(GOOD_FIXTURE_FOLDER, target)

    expected_path = target / "expected.json"
    doc = json.loads(expected_path.read_text(encoding="utf-8"))
    doc["document_id"] = folder_name
    doc["difficulty"] = _difficulty_for_basename(folder_name)
    expected_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return target


def _difficulty_for_basename(folder_name: str) -> str:
    """Pick a folder.schema.json-valid difficulty for the basename."""
    if folder_name.endswith("_easy"):
        return "easy"
    if folder_name.endswith("_medium"):
        return "medium"
    if folder_name.endswith("_missing_name"):
        return "missing_name"
    # Hard-class catch-all — covers calibration suffixes too.
    return "hard"


def write_sidecar(folder: Path, payload: dict) -> Path:
    """Write a ``semantic_table_truth.json`` under ``folder``.

    Returns the path of the written file.
    """
    p = folder / "semantic_table_truth.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p
