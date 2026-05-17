"""Feature 020 / T043 / FR-013 / FR-014 / MI-22 / MI-23: CPU-safe warn-
and-proceed tests for the ``--evidence-gate-skip-fallback`` opt-in flag.

Behavior matrix (per ``contracts/cli-contract.md`` §3 and
``contracts/module-invariants.md`` MI-22 / MI-23):

| Profile | --evidence-gate-skip-fallback | env var | Behavior         | stderr lines |
|---------|-------------------------------|---------|------------------|--------------|
| cpu     | unset                         | unset   | baseline         | 0            |
| cpu     | flag set                      | unset   | warn-and-proceed | 1            |
| cpu     | unset                         | =1      | warn-and-proceed | 1            |
| cpu     | flag set                      | =1      | warn-and-proceed | 1 (CLI wins) |

For every cell:

- Exit code matches the no-flag baseline (MI-23 — warn-and-proceed never
  changes the exit code).
- The four feature-020 ``run_summary`` fields are emitted with their
  default values per FR-014 (the GATE itself runs on CPU — only the
  skip-fallback BEHAVIOR is suppressed on non-GPU profiles).
- Exactly ONE stderr line carries the grep-able marker
  ``--evidence-gate-skip-fallback ignored:`` (MI-22 grep contract).

CPU-safe: mocks ``preprocessing.pipeline.run`` so the test suite stays
fast and does not touch PaddleOCR (mirrors the prior-features pattern
in ``test_cpu_warn_and_proceed.py``).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ledgerlinc_ocr.preprocessing import cli as cli_mod
from ledgerlinc_ocr.preprocessing.errors import EXIT_OK
from ledgerlinc_ocr.preprocessing.evidence_gate_optin import (
    EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR,
)


@pytest.fixture
def tmp_inv_folder(tmp_path: Path) -> Path:
    """Provide a writable folder with a copied real ``source.pdf`` so the
    CLI's input-validation passes without modifying the committed corpus
    baseline (FR-019 / SC-007). Mirrors test_cpu_warn_and_proceed.py."""
    import shutil

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


def _mock_pipeline_run_returning_minimal_artifact(folder: Path) -> MagicMock:
    """Mock ``preprocessing.pipeline.run`` so cli.main can complete without
    actually running PaddleOCR. The artifact is the minimal shape required
    for the CLI's post-run JSON read + run_summary emission to succeed.
    The evidence gate later evaluates this artifact (the ``pages: []``
    empty-page case maps to the negative-level signals; the gate decision
    is ``insufficient`` — that's expected and asserted in the body)."""
    artifact_path = folder / "preprocess_output.json"
    artifact_path.write_text(
        json.dumps(
            {
                "document_id": folder.name,
                "warnings": [],
                # Minimal pages list so the gate's loader sees a dict it
                # can recognize; an empty pages list is the
                # "insufficient" boundary case per spec §Edge Cases.
                "pages": [],
            }
        )
    )
    return MagicMock(return_value=artifact_path)


def _run_summary_from(captured_stdout: str) -> dict:
    """Extract the ``kind: "run_summary"`` line from captured stdout."""
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
# Baseline: no flag, no env — the comparison anchor for MI-23 exit-code
# parity.
# ---------------------------------------------------------------------------


def test_cpu_no_flag_baseline_exits_ok_and_emits_default_fields(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline: no ``--evidence-gate-skip-fallback`` flag, no truthy env.
    Zero ``--evidence-gate-skip-fallback ignored:`` lines on stderr;
    exit code 0; the four feature-020 fields ship with default values
    (FR-014 — the gate runs on CPU)."""
    monkeypatch.delenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, raising=False)
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
            ]
        )
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    assert "--evidence-gate-skip-fallback ignored:" not in captured.err
    summary = _run_summary_from(captured.out)
    # FR-014 / MI-16 / MI-17: all four feature-020 fields are always emitted.
    assert "evidence_gate_id" in summary
    assert summary["evidence_gate_id"] == "v1"
    assert "evidence_gate_state_counts" in summary
    assert set(summary["evidence_gate_state_counts"].keys()) == {
        "sufficient",
        "borderline",
        "insufficient",
    }
    assert "evidence_gate_documents" in summary
    assert isinstance(summary["evidence_gate_documents"], list)
    assert "evidence_gate_suppressed_fallback_count" in summary
    assert summary["evidence_gate_suppressed_fallback_count"] == 0


# ---------------------------------------------------------------------------
# T043 / MI-22 / MI-23 — CLI flag set on CPU → warn-and-proceed
# ---------------------------------------------------------------------------


def test_cpu_with_flag_warns_exactly_once_and_keeps_default_fields(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--evidence-gate-skip-fallback`` on ``ppstructurev3@cpu`` →
    exactly ONE stderr line with the grep-able marker (MI-22); same exit
    code as baseline (MI-23); the four feature-020 fields still emitted
    with defaults (FR-014); suppressed counter still 0 because no
    suppression happens on CPU."""
    monkeypatch.delenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, raising=False)
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
                "--evidence-gate-skip-fallback",
            ]
        )
    assert exit_code == EXIT_OK  # MI-23 — exit code unchanged
    captured = capsys.readouterr()
    matching_lines = [
        line
        for line in captured.err.splitlines()
        if "--evidence-gate-skip-fallback ignored:" in line
    ]
    assert len(matching_lines) == 1, (
        f"expected exactly 1 stderr line with the MI-22 marker; got "
        f"{len(matching_lines)}: {captured.err!r}"
    )
    summary = _run_summary_from(captured.out)
    # FR-014: the four fields are present with default values — the
    # gate itself still runs on CPU; only the skip-fallback BEHAVIOR is
    # suppressed on non-GPU profiles.
    assert summary["evidence_gate_id"] == "v1"
    assert summary["evidence_gate_state_counts"] == {
        "sufficient": 0,
        "borderline": 0,
        "insufficient": 1,
    } or summary["evidence_gate_state_counts"] == {
        "sufficient": 0,
        "borderline": 0,
        "insufficient": 0,
    }
    # No suppression on CPU (warn-and-proceed nulled the opt-in).
    assert summary["evidence_gate_suppressed_fallback_count"] == 0


def test_cpu_with_flag_exit_code_matches_no_flag_baseline(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MI-23: exit code with the flag set on CPU MUST equal the exit
    code without the flag on the same fixture."""
    monkeypatch.delenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, raising=False)

    mock_a = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_a):
        exit_no_flag = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
            ]
        )
    capsys.readouterr()  # drain

    mock_b = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_b):
        exit_with_flag = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
                "--evidence-gate-skip-fallback",
            ]
        )
    capsys.readouterr()  # drain

    assert exit_no_flag == exit_with_flag, (
        f"MI-23 violation: exit code drift between no-flag ({exit_no_flag}) "
        f"and flag-set ({exit_with_flag}) CPU runs"
    )


# ---------------------------------------------------------------------------
# T043 — env-var fallback path
# (LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=1 on CPU also triggers warn)
# ---------------------------------------------------------------------------


def test_cpu_with_env_var_only_warns_exactly_once(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=1`` on CPU (no CLI flag)
    → exactly ONE stderr line with the MI-22 marker. The env-var path
    MUST trigger the same warn-and-proceed as the CLI flag (R-020.1
    precedence: CLI absent → env-var truthy → True)."""
    monkeypatch.setenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "1")
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
            ]
        )
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    matching_lines = [
        line
        for line in captured.err.splitlines()
        if "--evidence-gate-skip-fallback ignored:" in line
    ]
    assert len(matching_lines) == 1, (
        f"expected exactly 1 stderr line with the MI-22 marker via env-var; "
        f"got {len(matching_lines)}: {captured.err!r}"
    )
    summary = _run_summary_from(captured.out)
    assert summary["evidence_gate_id"] == "v1"
    assert summary["evidence_gate_suppressed_fallback_count"] == 0


def test_cpu_with_cli_flag_and_truthy_env_warns_exactly_once(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI flag + truthy env var on CPU → still exactly ONE stderr warn
    line (the warn is per-CLI-invocation, not per-source); MI-22 marker
    matches."""
    monkeypatch.setenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "yes")
    mock_run = _mock_pipeline_run_returning_minimal_artifact(tmp_inv_folder)
    with patch("ledgerlinc_ocr.preprocessing.cli.pipeline.run", mock_run):
        exit_code = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
                "--evidence-gate-skip-fallback",
            ]
        )
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    matching_lines = [
        line
        for line in captured.err.splitlines()
        if "--evidence-gate-skip-fallback ignored:" in line
    ]
    assert len(matching_lines) == 1
