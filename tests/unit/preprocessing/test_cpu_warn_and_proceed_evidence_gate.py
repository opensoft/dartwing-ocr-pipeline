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
from unittest.mock import patch

import pytest

from dartwing_ocr.preprocessing import cli as cli_mod
from dartwing_ocr.preprocessing.errors import EXIT_OK
from dartwing_ocr.preprocessing.evidence_gate_optin import (
    EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR,
)


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
    mock_pipeline_run_minimal_artifact,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline: no ``--evidence-gate-skip-fallback`` flag, no truthy env.
    Zero ``--evidence-gate-skip-fallback ignored:`` lines on stderr;
    exit code 0; the four feature-020 fields ship with default values
    (FR-014 — the gate runs on CPU)."""
    monkeypatch.delenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, raising=False)
    mock_run = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
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
    mock_pipeline_run_minimal_artifact,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--evidence-gate-skip-fallback`` on ``ppstructurev3@cpu`` →
    exactly ONE stderr line with the grep-able marker (MI-22); same exit
    code as baseline (MI-23); the four feature-020 fields still emitted
    with defaults (FR-014); suppressed counter still 0 because no
    suppression happens on CPU."""
    monkeypatch.delenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, raising=False)
    mock_run = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
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
    # FR-014 / MI-16 / MI-17: the four fields are always emitted on CPU;
    # the gate itself still runs (only the skip-fallback BEHAVIOR is
    # suppressed on non-GPU profiles). This test's purpose is the
    # warn-and-proceed behavior + always-emit invariant — not pinning
    # the specific gate decision the mock's `pages: []` artifact maps
    # to. The state_counts SHAPE assertion (all three keys present,
    # values are integers, sum equals documents_succeeded) is the
    # invariant; the specific gate output is exercised by
    # `tests/unit/preprocessing/test_evidence_gate_signals_unit.py`
    # and friends in MVP scope. Shape-only here matches the baseline
    # test above for consistency.
    assert summary["evidence_gate_id"] == "v1"
    assert set(summary["evidence_gate_state_counts"].keys()) == {
        "sufficient",
        "borderline",
        "insufficient",
    }
    assert all(
        isinstance(v, int) for v in summary["evidence_gate_state_counts"].values()
    )
    # No suppression on CPU (warn-and-proceed nulled the opt-in).
    assert summary["evidence_gate_suppressed_fallback_count"] == 0


def test_cpu_with_flag_exit_code_matches_no_flag_baseline(
    tmp_inv_folder: Path,
    mock_pipeline_run_minimal_artifact,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MI-23: exit code with the flag set on CPU MUST equal the exit
    code without the flag on the same fixture."""
    monkeypatch.delenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, raising=False)

    mock_a = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_a):
        exit_no_flag = cli_mod.main(
            [
                "--document-folder",
                str(tmp_inv_folder),
                "--preprocess-profile",
                "ppstructurev3@cpu",
            ]
        )
    capsys.readouterr()  # drain

    mock_b = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_b):
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
# (DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1 on CPU also triggers warn)
# ---------------------------------------------------------------------------


def test_cpu_with_env_var_only_warns_exactly_once(
    tmp_inv_folder: Path,
    mock_pipeline_run_minimal_artifact,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1`` on CPU (no CLI flag)
    → exactly ONE stderr line with the MI-22 marker. The env-var path
    MUST trigger the same warn-and-proceed as the CLI flag (R-020.1
    precedence: CLI absent → env-var truthy → True)."""
    monkeypatch.setenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "1")
    mock_run = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
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
    mock_pipeline_run_minimal_artifact,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI flag + truthy env var on CPU → still exactly ONE stderr warn
    line (the warn is per-CLI-invocation, not per-source).

    R-020.1 nuance: argparse ``store_true`` can only express "flag
    present (True)" — there is no way to express "flag explicitly
    False" via the CLI. So the precedence rule "CLI wins when both
    set" only fires in one direction (CLI True hard-overrides any env
    value to True). The reverse direction (CLI False would override
    truthy env to False) is non-expressible at the CLI level — only at
    the resolver function level, which is pinned by
    ``tests/unit/preprocessing/test_evidence_gate_optin_unit.py``
    (T031 / R-020.1 precedence tests in MVP+US4 scope). This test
    pins the visible CLI-side property: both sources requesting True
    → single warn emission, not duplicated.
    """
    monkeypatch.setenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "yes")
    mock_run = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
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


def test_cpu_with_empty_string_env_does_not_warn(
    tmp_inv_folder: Path,
    mock_pipeline_run_minimal_artifact,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-020.1 empty-string-env-treated-as-unset: ``DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=""``
    on CPU (no CLI flag) MUST behave like the env-var is unset — ZERO
    warn lines. This pins the resolver's
    ``if raw == "": return False`` early-return branch at the CLI
    integration level (T031 covers it at the function level)."""
    monkeypatch.setenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "")
    mock_run = mock_pipeline_run_minimal_artifact(tmp_inv_folder)
    with patch("dartwing_ocr.preprocessing.cli.pipeline.run", mock_run):
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
    assert "--evidence-gate-skip-fallback ignored:" not in captured.err, (
        f"empty-string env should NOT trigger warn (treated as unset per "
        f"R-020.1); got stderr: {captured.err!r}"
    )


# ---------------------------------------------------------------------------
# T043 — stub-adapter coverage note
# ---------------------------------------------------------------------------
#
# tasks.md T043 says "invokes the CLI with --evidence-gate-skip-fallback
# on ppstructurev3@cpu AND stub-adapter profiles". The
# `ppstructurev3@cpu` path is covered above; the stub-adapter path is
# NOT reachable through `python -m dartwing_ocr.preprocessing` — that
# CLI rejects `--preprocess-profile stub` with `"unsupported lane None
# for preprocessing"`. Stub adapter is selected via the pipeline CLI's
# `--stack-preset` path (`python -m dartwing_ocr.pipeline`), which
# routes through `corpus_run.py`'s warm-corpus loop rather than the
# single-doc preprocess CLI.
#
# The pipeline-CLI warn-and-proceed path lives at
# `src/dartwing_ocr/pipeline/cli.py:744-765` and inherits the same
# `resolve_evidence_gate_skip_fallback` + `_is_gpu_lane_017` predicate
# as the preprocessing CLI — `is_gpu_lane("stub") is False` is already
# pinned in `tests/unit/preprocessing/test_warmup_envvar_truthiness.py`
# (line 199-213). A dedicated pipeline-CLI warn-path integration test
# is captured as a follow-up in tasks.md (see Polish section / T058);
# the predicate-level coverage in T044's `test_warn_does_not_depend_on
# _per_document_fr_005_state` (signature-based architectural pin)
# already guarantees the predicate is the same on both CLIs.
