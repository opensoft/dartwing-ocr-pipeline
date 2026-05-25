"""US4 T055/T056/T057: --with-evaluator subprocess invocation tests.

Tests the evaluator_subprocess module directly + the orchestrator's
warn-and-skip / downgrade-only paths.
"""

from __future__ import annotations

import io
import json
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from dartwing_ocr.gpu_demo.evaluator_subprocess import invoke_evaluator
from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main_capture(argv: list[str]) -> tuple[int, str, str]:
    from dartwing_ocr.gpu_demo.cli import main

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


@pytest.fixture
def per_doc_no_sidecar(tmp_path: Path) -> Path:
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)
    return folder


@pytest.fixture
def per_doc_with_sidecar(tmp_path: Path) -> Path:
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)
    (folder / "semantic_table_truth.json").write_text(
        json.dumps({"document_id": "inv_test", "rows": []})
    )
    return folder


def test_invoke_evaluator_sidecar_missing(per_doc_no_sidecar: Path) -> None:
    """invoke_evaluator returns sidecar_missing=True when no sidecar exists."""
    result = invoke_evaluator(per_doc_no_sidecar)
    assert result.sidecar_missing is True
    assert result.semantic_table_quality_passed is None


def test_warn_and_skip_no_sidecar_via_cli(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc_no_sidecar: Path,
) -> None:
    """--with-evaluator without sidecar emits WARN; quality_status_source stays 'gate'."""
    patch_orchestrator_composer(stub_pipeline_composer())
    code, stdout, stderr = _invoke_main_capture([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc_no_sidecar),
        "--with-evaluator",
    ])
    assert code == ExitCode.SUCCESS
    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "success"
    assert parsed["quality_status_source"] == "gate"
    # WARN stderr line per FR-022 + audit-walkthrough Q11.
    warn_lines = [ln for ln in stderr.splitlines() if ln.startswith("WARN:")]
    assert any("semantic_table_truth.json" in ln for ln in warn_lines), (
        f"expected sidecar-missing WARN; got stderr:\n{stderr}"
    )


def test_evaluator_subprocess_failure_keeps_source_gate(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    monkeypatch,
    per_doc_with_sidecar: Path,
) -> None:
    """Subprocess non-zero exit → WARN, quality_status_source stays 'gate'."""
    from dartwing_ocr.gpu_demo import evaluator_subprocess as eval_mod

    # Force subprocess.run to return a non-zero exit code.
    def _fake_run(*args, **kwargs):
        completed = subprocess.CompletedProcess(args=args, returncode=1)
        completed.stdout = ""
        completed.stderr = "fake evaluator failure"
        return completed

    monkeypatch.setattr(eval_mod.subprocess, "run", _fake_run)
    patch_orchestrator_composer(stub_pipeline_composer())

    code, stdout, stderr = _invoke_main_capture([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc_with_sidecar),
        "--with-evaluator",
    ])
    assert code == ExitCode.SUCCESS
    parsed = json.loads(stdout)
    assert parsed["quality_status_source"] == "gate"
    # WARN message references subprocess failure.
    warn_lines = [ln for ln in stderr.splitlines() if ln.startswith("WARN:")]
    assert any("evaluator subprocess failed" in ln for ln in warn_lines)


def test_successful_evaluator_flips_source(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    monkeypatch,
    per_doc_with_sidecar: Path,
) -> None:
    """T2 (triage) — successful evaluator → quality_status_source flips to 'evaluator'.

    The orchestrator's full ``--with-evaluator`` wiring (subprocess invocation
    → reading evaluation_document.json → ``EvaluatorVerdict`` →
    ``quality_status_source = "evaluator"``) was previously untested end-to-end.
    Every prior CLI test for ``--with-evaluator`` forced failure (sidecar
    missing or non-zero exit), so the success path was only unit-tested.
    """
    from dartwing_ocr.gpu_demo import evaluator_subprocess as eval_mod

    # Stub subprocess.run to "succeed" without actually invoking python -m
    # dartwing_ocr.evaluator; then pre-write the evaluation_document.json that
    # the evaluator would normally produce.
    def _fake_run(*args, **kwargs):
        completed = subprocess.CompletedProcess(args=args, returncode=0)
        completed.stdout = ""
        completed.stderr = ""
        return completed

    monkeypatch.setattr(eval_mod.subprocess, "run", _fake_run)
    (per_doc_with_sidecar / "evaluation_document.json").write_text(
        json.dumps({
            "document_id": per_doc_with_sidecar.name,
            "semantic_table_quality": {"passed": True},
        })
    )
    patch_orchestrator_composer(stub_pipeline_composer())

    code, stdout, stderr = _invoke_main_capture([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc_with_sidecar),
        "--with-evaluator",
    ])
    assert code == ExitCode.SUCCESS
    parsed = json.loads(stdout)
    assert parsed["runtime_outcome"] == "success"
    # The headline assertion: source MUST be "evaluator" when a verdict was read.
    assert parsed["quality_status_source"] == "evaluator", (
        f"expected source=evaluator; got {parsed['quality_status_source']}\n"
        f"full report: {parsed}"
    )
