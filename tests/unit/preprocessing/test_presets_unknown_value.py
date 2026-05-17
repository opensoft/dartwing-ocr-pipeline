"""Feature 017 (T015): CPU-safe fail-fast tests for unknown preset values.

Per R-017.9 / R-017.12 / Plan §I-10 / I-11: an unknown `module_set_id`
or `det_rec_variant_id` value passed via `--module-set` /
`--det-rec-variant` (or via the corresponding env vars) must fail fast
at the CLI parse boundary BEFORE any Paddle import. Exit code is 16
(`ExitCode.UNKNOWN_PRESET`); stderr names the valid values; no
`run_summary` line is emitted.

These tests invoke the preprocess CLI's `main(argv)` function directly
(no subprocess) so they run cleanly on any CPU host.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dartwing_ocr.pipeline.exit_codes import ExitCode
from dartwing_ocr.preprocessing.cli import main as preprocess_main


# ---------------------------------------------------------------------------
# Plan §I-10 / R-017.12: unknown values fail fast with exit code 16
# ---------------------------------------------------------------------------


def test_unknown_module_set_value_returns_exit_16(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--module-set=reduced-v99` exits 16 with stderr naming valid values."""
    # Pre-create a minimal document folder so we don't trigger
    # input-validation errors before the preset check
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    rc = preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--module-set",
            "reduced-v99",
        ]
    )
    captured = capsys.readouterr()
    assert rc == int(ExitCode.UNKNOWN_PRESET) == 16, (
        f"expected exit 16 (UNKNOWN_PRESET); got {rc} with stderr: {captured.err}"
    )
    # Stderr names the axis, the bad value, and the valid alternatives
    assert "unknown module_set:" in captured.err
    assert "'reduced-v99'" in captured.err
    assert "legacy" in captured.err
    assert "reduced-v1" in captured.err


def test_unknown_det_rec_variant_value_returns_exit_16(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--det-rec-variant=ppocrv9_imaginary` exits 16 with stderr naming
    valid values."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    rc = preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--det-rec-variant",
            "ppocrv9_imaginary",
        ]
    )
    captured = capsys.readouterr()
    assert rc == int(ExitCode.UNKNOWN_PRESET) == 16
    assert "unknown det_rec_variant:" in captured.err
    assert "'ppocrv9_imaginary'" in captured.err
    assert "legacy" in captured.err
    assert "ppocrv5-mobile" in captured.err
    assert "ppocrv4-mobile" in captured.err


# ---------------------------------------------------------------------------
# Plan §I-11: fail-fast wins over warn-and-proceed when both apply
# ---------------------------------------------------------------------------


def test_unknown_value_on_cpu_profile_fails_fast_not_warn(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When BOTH apply (CPU profile + unknown identifier value), fail-fast
    wins — operator gets exit 16 + unknown-value stderr line, NOT the
    cross-profile warn-and-proceed line (Plan §I-11)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    rc = preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--module-set",
            "Reduced-V1",  # mixed case — case-sensitive lookup rejects
        ]
    )
    captured = capsys.readouterr()
    assert rc == 16
    assert "unknown module_set:" in captured.err
    # NOT the warn-and-proceed line
    assert "--module-set ignored:" not in captured.err


# ---------------------------------------------------------------------------
# R-017.12: no run_summary emitted on fail-fast path
# ---------------------------------------------------------------------------


def test_no_run_summary_emitted_on_unknown_preset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No `kind: "run_summary"` JSON line on stdout when the run exits
    with UNKNOWN_PRESET (R-017.12)."""
    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    rc = preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--module-set",
            "garbage-not-a-real-preset",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 16
    # No run_summary line on stdout
    assert '"kind":"run_summary"' not in captured.out
    assert '"kind": "run_summary"' not in captured.out


# ---------------------------------------------------------------------------
# Pipeline (warm-corpus) CLI also fails fast
# ---------------------------------------------------------------------------


def test_pipeline_cli_unknown_module_set_returns_exit_16(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same fail-fast contract on the warm-corpus CLI's `run`
    subcommand."""
    from dartwing_ocr.pipeline.cli import main as pipeline_main

    docs = tmp_path / "documents.txt"
    docs.write_text("dummy\n")  # content irrelevant — fail-fast happens before parsing

    rc = pipeline_main(
        [
            "run",
            "--documents-file",
            str(docs),
            "--module-set",
            "reduced-v99",
        ]
    )
    captured = capsys.readouterr()
    assert rc == int(ExitCode.UNKNOWN_PRESET) == 16, (
        f"expected exit 16 from pipeline CLI; got {rc} stderr={captured.err}"
    )
    assert "unknown module_set:" in captured.err
