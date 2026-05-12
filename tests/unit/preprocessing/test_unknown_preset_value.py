"""Feature 018 (T013 / T026 / R-018.12 / contracts/cli-contract.md §3 §4):
unknown-preset fail-fast CLI tests for the two new feature-018 axes.

Mirrors feature 017's `test_presets_unknown_value.py` for the existing
`module_set` and `det_rec_variant` axes; this file extends coverage to
the two new axes added by feature 018:

- `--raster-profile=<unknown>` (T013, US1)
- `--region-strategy=<unknown>` (T026, US2)

Behavior under test (per cli-contract.md §3 / R-018.12):
- Exit code 16 (`UnknownPresetError.exit_code` reused from feature 017
  via the additive widening of `preset_axis: Literal[…]`).
- stderr contains the literal `error: unknown <preset_axis>: <value!r>`
  prefix and lists all valid values for that axis.
- NO `kind: "run_summary"` line is emitted on stdout (R-018.12 — fail
  happens BEFORE Paddle import / engine construction / artifact write).

All tests are CPU-safe (no Paddle import required by the test itself —
the CLI's preset-resolution path raises before Paddle import).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _invoke_cli(*flags: str) -> subprocess.CompletedProcess[str]:
    """Invoke the preprocessing CLI as a subprocess and return the
    completed process. We use a subprocess (not in-process main()) so
    the exit code propagates through the standard sys.exit path.

    A 30s timeout guards against runaway subprocesses freezing the suite
    (pre-PR QA review #3 — subprocess tests must not block indefinitely)."""
    cmd = [sys.executable, "-m", "ledgerlinc_ocr.preprocessing"] + list(flags)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# T013 / R-018.12: --raster-profile fail-fast
# ---------------------------------------------------------------------------


def test_unknown_raster_profile_exits_16(tmp_path: Path) -> None:
    """`--raster-profile=reduced-v99` exits with code 16 (R-018.12)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    result = _invoke_cli(
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--raster-profile",
        "reduced-v99",
    )
    assert result.returncode == 16, (
        f"expected exit 16, got {result.returncode}; "
        f"stderr={result.stderr!r}; stdout={result.stdout!r}"
    )


def test_unknown_raster_profile_stderr_lists_valid_values(tmp_path: Path) -> None:
    """The stderr line MUST contain `error: unknown raster_profile:`
    and list all four valid values (per cli-contract.md §3)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    result = _invoke_cli(
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--raster-profile",
        "reduced-v99",
    )
    assert "error: unknown raster_profile:" in result.stderr
    assert "'reduced-v99'" in result.stderr
    for valid in ["legacy", "reduced-v1", "cpu-default", "stub-default"]:
        assert valid in result.stderr, (
            f"stderr must list valid value {valid!r}; got {result.stderr!r}"
        )


def test_unknown_raster_profile_emits_no_run_summary(tmp_path: Path) -> None:
    """On the fail-fast path, NO `kind: "run_summary"` line is emitted
    on stdout (R-018.12 — fail happens BEFORE Paddle import / engine
    construction / artifact write)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    result = _invoke_cli(
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--raster-profile",
        "reduced-v99",
    )
    assert '"kind": "run_summary"' not in result.stdout
    assert '"kind":"run_summary"' not in result.stdout


# ---------------------------------------------------------------------------
# T013 / R-018.1: env-var fallback also fails fast on unknown value
# ---------------------------------------------------------------------------


def test_unknown_raster_profile_via_env_var_exits_16(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`LEDGERLINC_RASTER_PROFILE=reduced-v99` (env var, no CLI flag)
    exits with code 16 (R-018.1 / R-018.12 — env-var literal-value
    handling). Verifies the env-var fallback flows through the same
    `resolve_raster_profile` path as the CLI flag."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    monkeypatch.setenv("LEDGERLINC_RASTER_PROFILE", "reduced-v99")
    cmd = [
        sys.executable,
        "-m",
        "ledgerlinc_ocr.preprocessing",
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 16
    assert "error: unknown raster_profile:" in result.stderr


# ---------------------------------------------------------------------------
# T026 / R-018.12: --region-strategy fail-fast (US2)
# ---------------------------------------------------------------------------


def test_unknown_region_strategy_exits_16(tmp_path: Path) -> None:
    """`--region-strategy=header-first-v99` exits with code 16
    (R-018.12). Reuses feature 017's exit code 16 (no new code added —
    `UnknownPresetError.preset_axis: Literal[…]` widened additively)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    result = _invoke_cli(
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--region-strategy",
        "header-first-v99",
    )
    assert result.returncode == 16, (
        f"expected exit 16, got {result.returncode}; "
        f"stderr={result.stderr!r}; stdout={result.stdout!r}"
    )


def test_unknown_region_strategy_stderr_lists_valid_values(tmp_path: Path) -> None:
    """The stderr line MUST contain `error: unknown region_strategy:`
    and list all four valid values (per cli-contract.md §3)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    result = _invoke_cli(
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--region-strategy",
        "header-first-v99",
    )
    assert "error: unknown region_strategy:" in result.stderr
    assert "'header-first-v99'" in result.stderr
    for valid in ["full-page", "header-first-v1", "cpu-default", "stub-default"]:
        assert valid in result.stderr, (
            f"stderr must list valid value {valid!r}; got {result.stderr!r}"
        )


def test_unknown_region_strategy_emits_no_run_summary(tmp_path: Path) -> None:
    """On the fail-fast path, NO `kind: "run_summary"` line is emitted."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    result = _invoke_cli(
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--region-strategy",
        "header-first-v99",
    )
    assert '"kind": "run_summary"' not in result.stdout
    assert '"kind":"run_summary"' not in result.stdout


def test_unknown_region_strategy_via_env_var_exits_16(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`LEDGERLINC_REGION_STRATEGY=header-first-v99` (env var, no CLI
    flag) exits with code 16 (R-018.1 / R-018.12)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    monkeypatch.setenv("LEDGERLINC_REGION_STRATEGY", "header-first-v99")
    cmd = [
        sys.executable,
        "-m",
        "ledgerlinc_ocr.preprocessing",
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 16
    assert "error: unknown region_strategy:" in result.stderr


# ---------------------------------------------------------------------------
# Feature 019 / T016 / R-019.12: preprocess_strategy axis fail-fast
# ---------------------------------------------------------------------------


def test_unknown_preprocess_strategy_exits_16(tmp_path: Path) -> None:
    """`--preprocess-strategy=ocr-only-v99` exits with code 16 + stderr
    line + no run_summary emitted (R-019.12 / I-019.1)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    cmd = [
        sys.executable,
        "-m",
        "ledgerlinc_ocr.preprocessing",
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--preprocess-strategy",
        "ocr-only-v99",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 16


def test_unknown_preprocess_strategy_stderr_lists_valid_values(
    tmp_path: Path,
) -> None:
    """stderr line MUST contain `error: unknown preprocess_strategy:` and
    the two user-selectable values per contracts/cli-contract.md §4."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    cmd = [
        sys.executable,
        "-m",
        "ledgerlinc_ocr.preprocessing",
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--preprocess-strategy",
        "ocr-only-v99",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    assert "error: unknown preprocess_strategy:" in result.stderr
    for v in ("ppstructurev3", "ocr-only-v1"):
        assert v in result.stderr
    assert "cpu-default" not in result.stderr
    assert "stub-default" not in result.stderr


def test_unknown_preprocess_strategy_emits_no_run_summary(
    tmp_path: Path,
) -> None:
    """On unknown preset value the CLI exits BEFORE any run_summary is
    emitted (I-019.1)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    cmd = [
        sys.executable,
        "-m",
        "ledgerlinc_ocr.preprocessing",
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
        "--preprocess-strategy",
        "ocr-only-v99",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    assert '"kind": "run_summary"' not in result.stdout
    assert '"kind":"run_summary"' not in result.stdout


def test_unknown_preprocess_strategy_via_env_var_exits_16(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`LEDGERLINC_PREPROCESS_STRATEGY=ocr-only-v99` env var (no CLI
    flag) exits with code 16 (R-019.1 / R-019.12)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%fake\n")
    monkeypatch.setenv("LEDGERLINC_PREPROCESS_STRATEGY", "ocr-only-v99")
    cmd = [
        sys.executable,
        "-m",
        "ledgerlinc_ocr.preprocessing",
        "--document-folder",
        str(folder),
        "--preprocess-profile",
        "ppstructurev3@cpu",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)
    assert result.returncode == 16
    assert "error: unknown preprocess_strategy:" in result.stderr
