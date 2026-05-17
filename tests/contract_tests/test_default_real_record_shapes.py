"""US1 Acceptance Scenario 3: stdout/stderr shapes preserved under default
real run. FR-002 / Research R-010.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


def test_cold_default_run_stdout_record_shape_preserves_002(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Acceptance Scenario 3: stdout success summary keeps the 002 shape
    even after 011's CLI surface expansion.

    This test does not require live adapters because it verifies the
    *shape* of the stdout record, not the substance of the artifacts.
    Stub profiles produce a schema-valid record with the same key set.
    """
    from dartwing_ocr.pipeline.cli import main

    src = CORPUS_ROOT / "inv_001_easy" / "source.pdf"
    if not src.exists():
        pytest.skip(f"missing corpus PDF: {src}")
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    shutil.copy(src, folder / "source.pdf")

    code = main([
        "run",
        "--document-folder", str(folder),
        "--preprocess-profile", "stub",
        "--extract-profile", "stub",
        "--routing-profile", "stub",
        "--final-payload-profile", "stub",
        "--overwrite",
    ])
    assert code == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    # 002 key set -- no `kind` field, no `schema_version`.
    assert set(record.keys()) == {
        "document_id",
        "decision",
        "manual_review_required",
        "review_reason",
        "artifacts",
    }
