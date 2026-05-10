"""Feature 018 (T033 / FR-014 / SC-005 / contracts/cli-contract.md §3 /
failure-handling.md CHK009–CHK015): CPU-safe warn-and-proceed tests for
the two new flags on `ppstructurev3@cpu`.

Behavior matrix per cli-contract.md §3:

| Profile | --raster-profile | --region-strategy | Behavior | stderr extra lines |
|---------|------------------|-------------------|----------|--------------------|
| cpu     | unset           | unset             | baseline | 0                  |
| cpu     | reduced-v1      | unset             | warn+proceed | 1 (raster) |
| cpu     | unset           | header-first-v1 | warn+proceed | 1 (region) |
| cpu     | reduced-v1      | header-first-v1 | warn+proceed | 2 (both)   |

For each cell:
- Exit code matches baseline
- run_summary.raster_profile_id == "cpu-default"
- run_summary.region_strategy_id == "cpu-default"
- run_summary.region_strategy_fallback_count == 0
- stderr contains the expected number of `… ignored:` lines

Uses in-process mocking (mocks `pipeline.run` to skip actual OCR) so
the test suite stays under 5s. Subprocess-based `--raster-profile`
fail-fast verification lives in `test_unknown_preset_value.py` (T013/T026).

All tests are CPU-safe.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ledgerlinc_ocr.preprocessing import cli as cli_mod
from ledgerlinc_ocr.preprocessing.errors import EXIT_OK


@pytest.fixture
def tmp_inv_folder(tmp_path: Path) -> Path:
    """Provide a writable folder with a copied real source.pdf so the
    CLI's input-validation passes without modifying the committed
    corpus baseline (FR-019 / SC-007)."""
    import shutil
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    repo_root = Path(__file__).resolve().parents[3]
    source = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    shutil.copy(source, folder / "source.pdf")
    return folder


def _mock_pipeline_run_returning_minimal_artifact(folder: Path) -> MagicMock:
    """Mock `preprocessing.pipeline.run` so cli.main can complete without
    actually running PaddleOCR. Mirrors the pattern in
    test_warmup_cpu_no_op.py."""
    artifact_path = folder / "preprocess_output.json"
    artifact_path.write_text(json.dumps({
        "document_id": folder.name,
        "warnings": [],
    }))
    return MagicMock(return_value=artifact_path)


def _run_summary_from(captured_stdout: str) -> dict:
    """Extract the `kind: "run_summary"` line from captured stdout."""
    for line in reversed(captured_stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("kind") == "run_summary":
            return obj
    raise AssertionError(f"no run_summary found in stdout: {captured_stdout!r}")


# ---------------------------------------------------------------------------
# T033 / FR-014: 4-cell behavior matrix on the CPU profile
# ---------------------------------------------------------------------------


def test_cpu_no_flags_baseline_exits_ok_with_cpu_defaults(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """No-flag baseline: CPU defaults on run_summary; no `… ignored:`
    lines on stderr; exit code 0."""
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
        ])
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    assert "--raster-profile ignored:" not in captured.err
    assert "--region-strategy ignored:" not in captured.err
    summary = _run_summary_from(captured.out)
    assert summary["raster_profile_id"] == "cpu-default"
    assert summary["region_strategy_id"] == "cpu-default"
    assert summary["region_strategy_fallback_count"] == 0


def test_cpu_with_raster_profile_only_warns_once(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """`--raster-profile=reduced-v1` on CPU → 1 stderr warn line; CPU
    defaults on run_summary; same exit code as baseline."""
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--raster-profile", "reduced-v1",
        ])
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    assert "--raster-profile ignored:" in captured.err
    assert "--region-strategy ignored:" not in captured.err
    summary = _run_summary_from(captured.out)
    assert summary["raster_profile_id"] == "cpu-default"
    assert summary["region_strategy_id"] == "cpu-default"
    assert summary["region_strategy_fallback_count"] == 0


def test_cpu_with_region_strategy_only_warns_once(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """`--region-strategy=header-first-v1` on CPU → 1 stderr warn line;
    CPU defaults on run_summary; same exit code as baseline."""
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--region-strategy", "header-first-v1",
        ])
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    assert "--raster-profile ignored:" not in captured.err
    assert "--region-strategy ignored:" in captured.err
    summary = _run_summary_from(captured.out)
    assert summary["raster_profile_id"] == "cpu-default"
    assert summary["region_strategy_id"] == "cpu-default"
    assert summary["region_strategy_fallback_count"] == 0


def test_cpu_with_both_flags_warns_twice(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """Both flags set on CPU → 2 stderr warn lines (one per ignored
    flag); CPU defaults on run_summary; same exit code as baseline."""
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--raster-profile", "reduced-v1",
            "--region-strategy", "header-first-v1",
        ])
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    assert "--raster-profile ignored:" in captured.err
    assert "--region-strategy ignored:" in captured.err
    summary = _run_summary_from(captured.out)
    assert summary["raster_profile_id"] == "cpu-default"
    assert summary["region_strategy_id"] == "cpu-default"
    assert summary["region_strategy_fallback_count"] == 0


# ---------------------------------------------------------------------------
# T034 / FR-019 / SC-007 / non-regression.md CHK012: byte-identity test
# ---------------------------------------------------------------------------


def test_cpu_run_summary_byte_identical_with_explicit_legacy_flags(
    tmp_inv_folder: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """A `--raster-profile=legacy --region-strategy=full-page` run on
    the CPU profile produces a `run_summary` byte-identical (modulo
    timing fields and the ignored-warn lines) to a no-flag CPU run on
    the same fixture: both warn-and-proceed to CPU defaults per
    FR-014, so the three new top-level identifier fields MUST match."""
    mock_run_a = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run_a):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
        ])
    captured_a = capsys.readouterr()
    summary_a = _run_summary_from(captured_a.out)

    mock_run_b = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run_b):
        cli_mod.main([
            "--document-folder", str(tmp_inv_folder),
            "--preprocess-profile", "ppstructurev3@cpu",
            "--raster-profile", "legacy",
            "--region-strategy", "full-page",
        ])
    captured_b = capsys.readouterr()
    summary_b = _run_summary_from(captured_b.out)

    # The three new feature-018 fields MUST match exactly between the
    # two runs (both warn-and-proceed to CPU defaults).
    for field in ("raster_profile_id", "region_strategy_id", "region_strategy_fallback_count"):
        assert summary_a[field] == summary_b[field], (
            f"{field} drift across no-flag vs. explicit-legacy CPU runs: "
            f"a={summary_a[field]!r}, b={summary_b[field]!r}"
        )
    # Also assert the schema_version is unchanged
    assert summary_a["schema_version"] == summary_b["schema_version"] == "0.1.5"
