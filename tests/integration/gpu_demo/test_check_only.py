"""US1/US2: --check-only readiness-only mode tests (subset of T023/T024 that
land cleanly without pipeline composition).

The orchestrator's ``--check-only`` path is fully wired in T034 — the full
pipeline composition (the four phases) is what's pending for the workstation
manual GPU smoke run. ``--check-only`` exercises readiness checks 1–6 with
stubs and emits a stable-shape DemoRunReport JSON line on stdout.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from dartwing_ocr.gpu_demo.cli import build_parser
from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    """Invoke the demo CLI via ``cli.main`` and capture stdout JSON."""
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


def test_check_only_pass_emits_stable_shape(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """``--check-only`` pass: exit 0, JSON line with all runtime fields null."""
    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.SUCCESS, f"expected SUCCESS, got {code}; stdout={stdout!r}"
    assert stdout.count("\n") == 1, "stdout MUST be one JSON line"

    parsed = json.loads(stdout)

    # Stable-shape rule: every top-level key present.
    expected_keys = {
        "kind", "schema_version", "pipeline_version", "run_id",
        "interpreter_path", "voter_config_path", "expected_extraction_model",
        "document_folder", "bounded_timeout_seconds", "readiness",
        "runtime_outcome", "stalled_phase", "failure_kind",
        "failing_check_name", "phase_timings", "total_runtime_seconds",
        "artifact_paths", "quality_status", "quality_status_source",
        "cpu_fallback_detection", "diagnostic",
    }
    assert set(parsed.keys()) == expected_keys, (
        f"missing/extra keys: missing={expected_keys - set(parsed)}, "
        f"extra={set(parsed) - expected_keys}"
    )

    # --check-only nullification per FR-025a + Q3.
    assert parsed["kind"] == "demo_run_report"
    assert parsed["schema_version"] == "0.1.0"
    assert parsed["runtime_outcome"] is None
    assert parsed["stalled_phase"] is None
    assert parsed["failure_kind"] is None
    assert parsed["failing_check_name"] is None
    assert parsed["document_folder"] is None  # --check-only ignores it
    assert parsed["quality_status"] is None
    assert parsed["quality_status_source"] is None
    assert parsed["total_runtime_seconds"] is None
    assert parsed["artifact_paths"] is None
    # phase_timings all four keys present, all null.
    assert set(parsed["phase_timings"].keys()) == {
        "preprocess", "extraction", "routing", "final_payload"
    }
    assert all(v is None for v in parsed["phase_timings"].values())

    # Readiness: 8 checks, checks 7-8 skipped under --check-only, 1-6 pass.
    checks = parsed["readiness"]["checks"]
    assert len(checks) == 8
    statuses = {c["name"]: c["status"] for c in checks}
    for infra in (
        "interpreter/venv", "paddle-rocm-preflight", "ollama-reachability",
        "ollama-version", "ollama-model-gpu-placement", "ollama-context-length",
    ):
        assert statuses[infra] == "pass", f"{infra} should pass: {statuses}"
    for skipped in ("artifact-schema-validation", "pipeline-runtime-timeout"):
        assert statuses[skipped] == "skipped"
    assert parsed["readiness"]["overall_passed"] is True


def test_check_only_fail_ollama_unreachable(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """When Ollama is unreachable, ``--check-only`` exits 1 with failing_check_name set."""
    import httpx

    def _connection_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection refused", request=request
        )

    ollama_http_stub(_connection_error)
    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.READINESS_FAILED

    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] is None
    assert parsed["failure_kind"] == "readiness-failed"
    assert parsed["failing_check_name"] == "ollama-reachability"
    # Later checks skipped per fixed-order skip rule.
    statuses = {c["name"]: c["status"] for c in parsed["readiness"]["checks"]}
    assert statuses["ollama-reachability"] == "fail"
    for later in (
        "ollama-version", "ollama-model-gpu-placement", "ollama-context-length",
        "artifact-schema-validation", "pipeline-runtime-timeout",
    ):
        assert statuses[later] == "skipped"


def test_invalid_voter_config_exits_2(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    tmp_path: Path,
) -> None:
    """Malformed voter-config YAML exits 2 (invalid input/usage) before readiness."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("not: yaml: : :")
    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(bad_yaml),
    ])
    assert code == ExitCode.INVALID_INPUT
    parsed = json.loads(stdout)
    assert parsed["failure_kind"] == "invalid-input"
    assert parsed["runtime_outcome"] is None
    assert parsed["failing_check_name"] is None
    # Readiness checks did NOT run.
    assert parsed["readiness"]["checks"] == []


def test_check_only_does_not_check_source_pdf(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    tmp_path: Path,
) -> None:
    """T049 + CHK037: --check-only passes even when per-doc folder has no source.pdf.

    --check-only is for infrastructure readiness only; per-doc state (incl. source.pdf)
    is not validated. A passing --check-only does NOT imply a subsequent full run will
    succeed.
    """
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()
    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(empty_folder),  # ignored under --check-only
    ])
    # Despite the empty document folder, --check-only passes (it ignores --document-folder).
    assert code == ExitCode.SUCCESS
    parsed = json.loads(stdout)
    assert parsed["document_folder"] is None  # --check-only nulls it
    assert parsed["runtime_outcome"] is None


def test_check_only_within_10s_warm(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    """T038 + SC-007: --check-only completes within 10 s warm (with stubs)."""
    import time

    start = time.monotonic()
    code, stdout = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    elapsed = time.monotonic() - start
    assert code == ExitCode.SUCCESS
    assert elapsed < 10.0, f"--check-only took {elapsed:.2f}s > 10s budget"
