"""Feature 018 (T031 / SC-004 / I-018.2 / I-018.9): CPU-safe identifier-
stability tests for the three new `run_summary` top-level fields.

SC-004 contract:
- Two runs with the same `(raster_profile_id, region_strategy_id)`
  configuration on the same input produce identical identifier values.
- On CPU/stub profiles, the threaded value is dropped via warn-and-
  proceed (FR-014); the run_summary identifier values stay at the
  CPU/stub defaults regardless of flag values (I-018.2).

Uses in-process mocking (mocks `pipeline.run` to skip actual OCR) so
the test suite stays under 5s.

All tests are CPU-safe (no Paddle import, no GPU dependency).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dartwing_ocr.preprocessing import cli as cli_mod


@pytest.fixture
def tmp_inv_folder(tmp_path: Path) -> Path:
    """Provide a writable folder with a copied real source.pdf."""
    import shutil
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    shutil.copy(source, folder / "source.pdf")
    return folder


def _mock_pipeline_run(folder: Path) -> MagicMock:
    """Mock `preprocessing.pipeline.run` to skip actual PaddleOCR."""
    artifact_path = folder / "preprocess_output.json"
    artifact_path.write_text(json.dumps({
        "document_id": folder.name,
        "warnings": [],
    }))
    return MagicMock(return_value=artifact_path)


def _run_summary_from(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("kind") == "run_summary":
            return obj
    raise AssertionError(f"no run_summary found in stdout: {stdout!r}")


# ---------------------------------------------------------------------------
# T031 / SC-004: identifier values stable across consecutive runs
# ---------------------------------------------------------------------------


def test_two_consecutive_cpu_runs_produce_identical_identifiers(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Two consecutive CPU runs with identical inputs produce identical
    values for all three new top-level fields (SC-004 within-
    configuration stability)."""
    mock_run_a = _mock_pipeline_run(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run_a):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
        ])
    captured_a = capsys.readouterr()
    summary_a = _run_summary_from(captured_a.out)

    mock_run_b = _mock_pipeline_run(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run_b):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
        ])
    captured_b = capsys.readouterr()
    summary_b = _run_summary_from(captured_b.out)

    for field in ("raster_profile_id", "region_strategy_id", "region_strategy_fallback_count"):
        assert summary_a[field] == summary_b[field], (
            f"{field} must be stable across identical runs: "
            f"got {summary_a[field]!r} then {summary_b[field]!r}"
        )


# ---------------------------------------------------------------------------
# T031 / I-018.2 / SC-005: CPU lane's identifiers reflect profile defaults
# regardless of flag values
# ---------------------------------------------------------------------------


def test_cpu_run_with_warn_and_proceed_flags_emits_cpu_defaults(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A run with `--raster-profile=reduced-v1 --region-strategy=header-first-v1`
    on `ppstructurev3@cpu` warn-and-proceeds (per FR-014); the
    run_summary identifier values MUST stay at CPU defaults regardless
    of flag values (I-018.2)."""
    mock_run_baseline = _mock_pipeline_run(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run_baseline):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
        ])
    captured_baseline = capsys.readouterr()
    baseline_summary = _run_summary_from(captured_baseline.out)

    mock_run_flagged = _mock_pipeline_run(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run_flagged):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--raster-profile", "reduced-v1",
            "--region-strategy", "header-first-v1",
        ])
    captured_flagged = capsys.readouterr()
    flagged_summary = _run_summary_from(captured_flagged.out)

    assert flagged_summary["raster_profile_id"] == "cpu-default"
    assert flagged_summary["region_strategy_id"] == "cpu-default"
    assert flagged_summary["region_strategy_fallback_count"] == 0
    for field in ("raster_profile_id", "region_strategy_id", "region_strategy_fallback_count"):
        assert flagged_summary[field] == baseline_summary[field], (
            f"{field} must be CPU-default-stable regardless of flags: "
            f"baseline={baseline_summary[field]!r}, flagged={flagged_summary[field]!r}"
        )
    assert "--raster-profile ignored:" in captured_flagged.err
    assert "--region-strategy ignored:" in captured_flagged.err
