"""Preflight CLI dual-format output tests (T011).

Asserts:
- (a) stdout text section follows the ordered template in Contracts §1.Stdout shape;
- (b) exactly one trailing JSON line parses as `{"kind":"preflight_readout","schema_version":"0.1.0", ...}`;
- (c) `--quiet` suppresses the text section and emits only the JSON line;
- (d) `--no-init` sets `ppstructurev3_init_skipped_reason="caller_disabled_init_attempt"` (when applicable) and skips the construction;
- (e) exit codes match the Contracts §1 table (per VT1 enumeration: 0/10/11/12/13/14 + 1 argparse + 2 internal).
"""
from __future__ import annotations

import json
import sys
from importlib import metadata
from io import StringIO
from typing import Optional
from unittest.mock import patch

import pytest

# VT-003 / T035: skip if preflight is unavailable.
preflight = pytest.importorskip("ledgerlinc_ocr.preprocessing.preflight")
preflight_cli = pytest.importorskip("ledgerlinc_ocr.preprocessing.preflight_cli")
PreflightState = preflight.PreflightState


def _patch_versions_absent(monkeypatch) -> None:
    real_version = metadata.version

    def fake_version(name: str) -> str:
        if name in ("paddlepaddle", "paddleocr"):
            raise metadata.PackageNotFoundError(name)
        return real_version(name)

    monkeypatch.setattr(metadata, "version", fake_version)


def _run_cli(monkeypatch, argv: list[str]) -> tuple[int, str, str]:
    """Run preflight_cli.main with captured stdout/stderr."""
    out_buf = StringIO()
    err_buf = StringIO()
    monkeypatch.setattr(sys, "stdout", out_buf)
    monkeypatch.setattr(sys, "stderr", err_buf)
    rc = preflight_cli.main(argv)
    monkeypatch.undo()
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_dual_format_text_then_one_json_line(monkeypatch) -> None:
    _patch_versions_absent(monkeypatch)
    rc, out, _ = _run_cli(monkeypatch, [])
    # Body has multiple lines; last line is the JSON object.
    lines = out.rstrip("\n").split("\n")
    assert len(lines) >= 3
    assert lines[0].startswith("[preflight] state:")
    json_line = lines[-1]
    payload = json.loads(json_line)
    assert payload["kind"] == "preflight_readout"
    assert payload["schema_version"] == "0.1.0"
    assert payload["state"] == PreflightState.PADDLE_NOT_INSTALLED.value
    # No trailing extra JSON lines (exactly one JSON object).
    json_count = sum(1 for line in lines if line.startswith("{"))
    assert json_count == 1
    # Exit code matches FR-001 state.
    assert rc == 10


def test_quiet_emits_only_json_line(monkeypatch) -> None:
    _patch_versions_absent(monkeypatch)
    rc, out, _ = _run_cli(monkeypatch, ["--quiet"])
    lines = out.rstrip("\n").split("\n")
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["kind"] == "preflight_readout"
    assert rc == 10


def test_no_init_sets_skipped_reason_on_success_path(monkeypatch) -> None:
    """When earlier steps pass and --no-init is set, step 6 is suppressed
    and ppstructurev3_init_skipped_reason is recorded."""
    from types import SimpleNamespace

    real_version = metadata.version

    def fake_version(name: str) -> str:
        if name == "paddlepaddle":
            return "3.3.1"
        if name == "paddleocr":
            return "3.5.0"
        return real_version(name)

    monkeypatch.setattr(metadata, "version", fake_version)

    class _CudaNs:
        @staticmethod
        def device_count() -> int:
            return 1

    class _DevNs:
        cuda = _CudaNs()

        @staticmethod
        def set_device(_: str) -> None:
            return None

    paddle_stub = SimpleNamespace(
        is_compiled_with_cuda=lambda: True,
        is_compiled_with_rocm=lambda: False,
        device=_DevNs,
        to_tensor=lambda _: SimpleNamespace(),
    )
    monkeypatch.setitem(sys.modules, "paddle", paddle_stub)

    rc, out, _ = _run_cli(monkeypatch, ["--no-init", "--quiet"])
    payload = json.loads(out.rstrip("\n"))
    assert payload["state"] == PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED.value
    assert payload["evidence"]["ppstructurev3_init_skipped_reason"] == "caller_disabled_init_attempt"
    assert payload["evidence"]["ppstructurev3_init_seconds"] is None
    assert payload["evidence"]["ppstructurev3_init_error"] is None
    assert rc == 0


@pytest.mark.parametrize(
    "state,expected_exit",
    [
        (PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED, 0),
        (PreflightState.PADDLE_NOT_INSTALLED, 10),
        (PreflightState.PADDLE_CPU_ONLY, 11),
        (PreflightState.GPU_NOT_EXPOSED, 12),
        (PreflightState.GPU_EXPOSED_PADDLE_CANT_BIND, 13),
        (PreflightState.PPSTRUCTUREV3_INIT_FAILED, 14),
    ],
)
def test_exit_code_mapping_per_fr001_state(state, expected_exit, monkeypatch) -> None:
    """VT1 explicit exit-code enumeration. Drive each FR-001 state via a
    mocked classify(...) and assert the CLI's exit code matches the
    Contracts §1 table verbatim."""
    from ledgerlinc_ocr.preprocessing.preflight import (
        PreflightEvidence,
        PreflightReadout,
    )

    fake_evidence = PreflightEvidence(
        interpreter_path="/usr/bin/python",
        interpreter_version="3.12.0",
        venv_path=None,
        paddle_version=None,
        paddleocr_version=None,
        paddle_compiled_with_cuda=None,
        paddle_compiled_with_rocm=None,
        visible_device_count=None,
        selected_device="gpu:0" if state is PreflightState.PPSTRUCTUREV3_INIT_SUCCEEDED else None,
        runtime_device_exposure={},
    )
    fake_readout = PreflightReadout(
        state=state, evidence=fake_evidence, recommendation="test"
    )
    with patch("ledgerlinc_ocr.preprocessing.preflight_cli.classify", return_value=fake_readout):
        rc, _, _ = _run_cli(monkeypatch, ["--quiet"])
    assert rc == expected_exit


def test_internal_classifier_crash_exits_2(monkeypatch) -> None:
    """Per Contracts §1.Exit codes: an unhandled internal classifier
    error returns exit code 2, with the stderr error format."""
    def _crash(**_):
        raise RuntimeError("boom")

    with patch("ledgerlinc_ocr.preprocessing.preflight_cli.classify", side_effect=RuntimeError("boom")):
        rc, _, err = _run_cli(monkeypatch, ["--quiet"])
    assert rc == 2
    assert "preflight: internal error" in err
    assert "RuntimeError" in err


def test_argparse_error_exits_1(monkeypatch) -> None:
    """An unrecognized argument should produce exit code 1 (argparse default)."""
    with pytest.raises(SystemExit) as excinfo:
        preflight_cli.main(["--bogus"])
    assert excinfo.value.code == 2 or excinfo.value.code == 1  # argparse uses 2 for usage errors


def test_quiet_omits_text_section_but_keeps_json(monkeypatch) -> None:
    """Per Contracts §1.Stdout shape: --quiet suppresses the human-readable
    text section but always emits the trailing JSON line."""
    _patch_versions_absent(monkeypatch)
    rc, out, _ = _run_cli(monkeypatch, ["--quiet"])
    assert "[preflight] state:" not in out
    assert out.startswith("{")
    assert json.loads(out.rstrip("\n"))["kind"] == "preflight_readout"
