"""Feature 017 (T029 / US4 / FR-013 / SC-004 / Plan §I-7 step 2):
CPU-safe warn-and-proceed tests.

Per FR-013 / contracts/cli-contract.md §3: when `--module-set` or
`--det-rec-variant` is set on a non-GPU profile (CPU, stub adapter),
the CLI emits one stderr warning line per ignored flag and proceeds
with the active profile's identity-preset behavior. The `module_set_id`
and `det_rec_variant_id` on the run_summary are `cpu-default` /
`stub-default` regardless of which value the operator passed.

Tests grep for the literal substrings `--module-set ignored:` and
`--det-rec-variant ignored:` so the wording can be tightened later
without breaking them.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_cpu_profile_module_set_known_value_emits_warn_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--module-set=reduced-v1` on `ppstructurev3@cpu` emits the
    FR-013 warn-and-proceed stderr line (literal `--module-set ignored:`
    substring) and returns the same exit status as a no-flag CPU run
    (the engine never receives the flag's effect)."""
    from ledgerlinc_ocr.preprocessing.cli import main as preprocess_main

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    # Note: the CPU run will fail with `EXIT_INPUT_REJECTED` or similar
    # because we're using a minimal stub PDF — but the warn line should
    # appear BEFORE that failure. We assert just on stderr here, not on
    # exit code.
    preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--module-set",
            "reduced-v1",
        ]
    )
    captured = capsys.readouterr()
    assert "--module-set ignored:" in captured.err
    # Specifically, the warning names the active profile (FR-013)
    assert "ppstructurev3@cpu" in captured.err
    # No fail-fast unknown-preset line — the value was known
    assert "unknown module_set:" not in captured.err


def test_cpu_profile_det_rec_variant_known_value_emits_warn_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--det-rec-variant=ppocrv5-mobile` on `ppstructurev3@cpu` emits
    the parallel `--det-rec-variant ignored:` warn line."""
    from ledgerlinc_ocr.preprocessing.cli import main as preprocess_main

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--det-rec-variant",
            "ppocrv5-mobile",
        ]
    )
    captured = capsys.readouterr()
    assert "--det-rec-variant ignored:" in captured.err
    assert "ppstructurev3@cpu" in captured.err
    assert "unknown det_rec_variant:" not in captured.err


def test_both_flags_set_on_cpu_emit_two_warn_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Setting both flags on CPU emits exactly two warn lines (one
    per ignored flag) per FR-013 / contracts/cli-contract.md §3."""
    from ledgerlinc_ocr.preprocessing.cli import main as preprocess_main

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
            "--module-set",
            "reduced-v1",
            "--det-rec-variant",
            "ppocrv5-mobile",
        ]
    )
    captured = capsys.readouterr()
    assert "--module-set ignored:" in captured.err
    assert "--det-rec-variant ignored:" in captured.err
    # Exactly two `ignored:` substrings
    assert captured.err.count("ignored:") == 2


def test_default_cpu_profile_no_flags_emits_no_warn_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A default CPU run with no preset flags emits no `ignored:` line
    on stderr (no flags to warn about)."""
    from ledgerlinc_ocr.preprocessing.cli import main as preprocess_main

    folder = tmp_path / "inv_001_easy"
    folder.mkdir()
    (folder / "source.pdf").write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    preprocess_main(
        [
            "--document-folder",
            str(folder),
            "--preprocess-profile",
            "ppstructurev3@cpu",
        ]
    )
    captured = capsys.readouterr()
    assert "ignored:" not in captured.err


def test_unknown_module_set_on_cpu_does_not_emit_warn_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Per Plan §I-11: when both apply (CPU profile + unknown value),
    fail-fast wins. The unknown-value path emits the `unknown module_set:`
    line but NOT the `--module-set ignored:` warn-and-proceed line."""
    from ledgerlinc_ocr.preprocessing.cli import main as preprocess_main

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
    assert rc == 16
    assert "unknown module_set:" in captured.err
    assert "--module-set ignored:" not in captured.err
