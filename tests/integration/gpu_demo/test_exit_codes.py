"""US2 T041: exit-code table coverage (FR-021).

Asserts each (`runtime_outcome`, `failure_kind`) combination produces the
matching exit code from the closed table:

    0 = success
    1 = readiness failed
    2 = invalid input/usage
    3 = pipeline runtime timeout
    4 = pipeline runtime error (incl. cpu-fallback-detected)
    5 = artifact schema validation failed

Combined with the readiness/runtime failure tests this covers every
documented exit code.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import httpx
import pytest

from dartwing_ocr.gpu_demo.exit_codes import ExitCode


def _invoke_main(argv: list[str]) -> tuple[int, str]:
    from dartwing_ocr.gpu_demo.cli import main

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


@pytest.fixture
def per_doc(tmp_path: Path) -> Path:
    src = (Path(__file__).parent / "fixtures" / "ok" / "source.pdf").resolve()
    folder = tmp_path / "inv_test"
    folder.mkdir()
    (folder / "source.pdf").symlink_to(src)
    return folder


def test_exit_0_success(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc: Path,
) -> None:
    patch_orchestrator_composer(stub_pipeline_composer())
    code, _ = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    assert code == ExitCode.SUCCESS == 0


def test_exit_1_readiness_failed(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    ollama_http_stub(handler)
    code, _ = _invoke_main([
        "--check-only",
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
    ])
    assert code == ExitCode.READINESS_FAILED == 1


def test_exit_2_invalid_input_voter_config(
    paddle_preflight_stub, ollama_http_stub, force_venv_interpreter, tmp_path: Path,
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: yaml: : :")
    code, _ = _invoke_main(["--check-only", "--voter-config", str(bad)])
    assert code == ExitCode.INVALID_INPUT == 2


def test_exit_2_invalid_input_missing_source_pdf(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    tmp_path: Path,
) -> None:
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()
    code, _ = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(empty_folder),
    ])
    assert code == ExitCode.INVALID_INPUT == 2


def test_exit_4_pipeline_runtime_error(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    bypass_schema_validation,
    patch_orchestrator_composer,
    per_doc: Path,
) -> None:
    """Stub composer raises mid-pipeline → exit 4 (pipeline-runtime-error)."""
    patch_orchestrator_composer(stub_pipeline_composer(fail_phase="extraction"))
    code, _ = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    assert code == ExitCode.PIPELINE_RUNTIME_ERROR == 4


def test_exit_5_schema_validation_failed(
    paddle_preflight_stub,
    ollama_http_stub,
    force_venv_interpreter,
    ok_fixture_folder: Path,
    stub_pipeline_composer,
    patch_orchestrator_composer,
    monkeypatch,
    per_doc: Path,
) -> None:
    """Force the schema validator to fail one artifact → exit 5."""
    from dartwing_ocr.gpu_demo.readiness import schema_validation as svm

    def _failing_validator(path):
        return f"forced failure: {path.name}"

    monkeypatch.setattr(svm, "_validate_artifact", _failing_validator)
    patch_orchestrator_composer(stub_pipeline_composer())
    code, _ = _invoke_main([
        "--voter-config", str(ok_fixture_folder / "voter_config.yaml"),
        "--document-folder", str(per_doc),
    ])
    assert code == ExitCode.ARTIFACT_SCHEMA_VALIDATION_FAILED == 5
