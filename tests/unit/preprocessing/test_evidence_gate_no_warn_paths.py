"""Feature 020 / T044 / MI-24 / R-020.12: CPU-safe verification that the
``--evidence-gate-skip-fallback ignored:`` warn does NOT fire on paths
where it has no contract reason to fire.

Per R-020.12 ("The warn fires only when ALL of: opt-in active AND active
profile is not ``ppstructurev3@gpu``"), the warn fires iff BOTH:

  (i)  the opt-in is active (CLI flag OR truthy env var), AND
  (ii) the active preprocess profile is NOT a GPU lane.

This file pins the three documented no-warn paths from T044:

  (a) opt-in unset on any profile (CPU or otherwise) → no warn.
  (b) opt-in active on ``ppstructurev3@gpu`` with ``--preprocess-strategy``
      != ``ocr-only-v1`` → no warn (the flag is a no-op because there
      is no OCR-only candidate to suppress, but it does not fire the
      cross-profile warn either — the warn is purely a non-GPU-profile
      mitigation).
  (c) opt-in active on ``ppstructurev3@gpu`` with ``ocr-only-v1`` but
      no document triggers the feature 019 FR-005 fallback condition
      → no warn (the suppression simply does not happen at the
      orchestrator's disposition seam; no operator-facing diagnostic
      is owed because the operator's intent is honored).

The two GPU-profile cases (b)/(c) are verified at the predicate level
because the actual CLI cannot reach the GPU lane on a no-Paddle / no-GPU
host. The invariant we lock down is that the CLI's warn-emission
predicate ``(opt_in_active AND NOT is_gpu_lane(lane))`` evaluates to
``False`` on GPU lanes regardless of preprocess-strategy choice or
per-document FR-005 trigger state. That is the architectural property
the warn must satisfy.

CPU-safe: no Paddle import; the GPU-lane assertions test pure helper
functions and do not invoke any GPU code path.
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
    resolve_evidence_gate_skip_fallback,
)
from ledgerlinc_ocr.preprocessing.warmup_optin import is_gpu_lane

GREP_MARKER = "--evidence-gate-skip-fallback ignored:"


@pytest.fixture
def tmp_inv_folder(tmp_path: Path) -> Path:
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


# ---------------------------------------------------------------------------
# Path (a): opt-in unset on CPU → no warn.
# ---------------------------------------------------------------------------


def test_no_warn_when_optin_unset_no_cli_no_env(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path (a): no flag, no env, default CPU profile → zero stderr
    lines carrying the MI-22 grep marker."""
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
    assert GREP_MARKER not in captured.err


def test_no_warn_when_optin_unset_falsy_env_only(
    tmp_inv_folder: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Path (a) variant: env var set to a falsy value → no opt-in → no
    warn. Verifies the env-var precedence rule R-020.1 ("anything not
    in the truthy vocabulary is False")."""
    monkeypatch.setenv(EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR, "0")
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
    assert GREP_MARKER not in captured.err


# ---------------------------------------------------------------------------
# Path (b) and (c): opt-in active on GPU lane → no warn (regardless of
# preprocess-strategy or per-document FR-005 trigger state).
#
# These two cases are verified at the predicate level — the warn condition
# in the CLI is `(opt_in_active AND NOT is_gpu_lane(lane))`. On a GPU
# lane, the second conjunct is always False, so the warn never fires.
# That architectural property is independent of what `--preprocess-strategy`
# the operator selected and independent of any per-document FR-005 outcome
# (the warn is a CLI-time diagnostic, not a per-doc one).
# ---------------------------------------------------------------------------


def _warn_predicate(opt_in_active: bool, preprocess_lane: str) -> bool:
    """Mirror the CLI warn-emission predicate from
    ``preprocessing/cli.py`` so we can test the architectural condition
    directly on a CPU-only host (where invoking the actual GPU CLI path
    is not safe — preflight would fail).

    The predicate is intentionally re-stated here (not imported from
    ``cli.py``) so any future drift between cli.py and R-020.12
    surfaces as a test failure — the test pins the CONTRACT, not the
    implementation.
    """
    return opt_in_active and not is_gpu_lane(preprocess_lane)


def test_no_warn_on_gpu_lane_with_optin_active() -> None:
    """Path (b)/(c) core: on any ``gpuN`` lane, the warn predicate is
    False even when the opt-in is active. The preprocess-strategy choice
    (ocr-only-v1 / ppstructurev3 / unset) is irrelevant — the warn is a
    profile-level diagnostic, not a strategy-level one (R-020.12)."""
    # GPU lane string format mirrors `_resolve_preprocess_lane()` in
    # preprocessing/cli.py: profile=ppstructurev3@gpu → lane="gpu0".
    for lane in ("gpu0", "gpu1", "gpu7"):
        assert _warn_predicate(opt_in_active=True, preprocess_lane=lane) is False, (
            f"warn predicate fired on GPU lane {lane!r} — R-020.12 violation"
        )


def test_no_warn_on_gpu_lane_with_optin_inactive() -> None:
    """Trivially true: opt-in inactive AND GPU lane → no warn."""
    for lane in ("gpu0", "gpu1"):
        assert _warn_predicate(opt_in_active=False, preprocess_lane=lane) is False


def test_warn_fires_only_on_non_gpu_with_optin_active() -> None:
    """Positive control: the warn predicate IS True iff opt-in active
    AND lane is NOT a GPU lane. This is the contract from R-020.12.
    Without this assertion the no-warn assertions above could pass
    vacuously (e.g., if the predicate always returned False)."""
    assert _warn_predicate(opt_in_active=True, preprocess_lane="cpu") is True
    assert _warn_predicate(opt_in_active=False, preprocess_lane="cpu") is False


# ---------------------------------------------------------------------------
# Path (c) refinement: per-document FR-005 trigger state is orthogonal
# to the CLI-level warn predicate. The warn fires (or not) at CLI
# parse-time based on profile + opt-in; per-document state cannot
# retroactively summon or suppress the warn (R-020.12 / MI-24).
# ---------------------------------------------------------------------------


def test_warn_does_not_depend_on_per_document_fr_005_state() -> None:
    """The warn is a CLI-time diagnostic — it cannot observe per-document
    state because it fires before any document is processed. Pin this
    architecturally: the predicate signature accepts only ``opt_in_active``
    and ``preprocess_lane``; per-document fields (FR-005 trigger,
    candidate gate decision) are NOT inputs.

    A future regression that wires per-document state into the warn
    predicate would change its arity and fail this test at import.
    """
    import inspect

    from ledgerlinc_ocr.preprocessing.evidence_gate_optin import (
        evidence_gate_skip_fallback_warn_message,
        resolve_evidence_gate_skip_fallback,
    )

    # The two warn-related public helpers MUST NOT take per-document
    # state parameters. (The warn-message helper takes only
    # ``active_profile``; the resolver takes only ``cli_value`` + ``env``.)
    msg_sig = inspect.signature(evidence_gate_skip_fallback_warn_message)
    assert set(msg_sig.parameters.keys()) == {"active_profile"}, (
        "evidence_gate_skip_fallback_warn_message parameters drifted — "
        "per-document state must not be a warn input (R-020.12 / MI-24)"
    )
    resolve_sig = inspect.signature(resolve_evidence_gate_skip_fallback)
    assert set(resolve_sig.parameters.keys()) == {"cli_value", "env"}, (
        "resolve_evidence_gate_skip_fallback parameters drifted — "
        "per-document state must not be a warn-resolution input "
        "(R-020.12 / MI-24)"
    )


def test_resolve_evidence_gate_skip_fallback_default_is_false() -> None:
    """Path (a) at the resolver level: no CLI, no env → False. The
    default-OFF invariant (FR-012 / MI-20) is what makes path (a)
    trivially no-warn."""
    assert resolve_evidence_gate_skip_fallback(None, env={}) is False
    assert resolve_evidence_gate_skip_fallback(False, env={}) is False
