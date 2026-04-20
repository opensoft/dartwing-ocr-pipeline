"""T013a: Ollama endpoint precedence (flag > env > default)."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import CLIInvocation, RunResult, Runner
from ledgerlinc_ocr.pipeline.exit_codes import ExitCode


class _CapturingRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.invocation: CLIInvocation | None = None

    def run(self, invocation: CLIInvocation) -> RunResult:
        self.invocation = invocation
        return RunResult(
            exit_code=ExitCode.SUCCESS,
            artifacts_written=[],
            stage="schema_validation",
            message="",
            routing_decision={
                "decision": "edge_accept",
                "review_status": {
                    "manual_review_required": False,
                    "review_reason": None,
                },
            },
        )


def _invoke(
    tmp_document_folder: Callable[..., Path], argv_extra: list[str]
) -> _CapturingRunner:
    folder = tmp_document_folder(1, "easy")
    r = _CapturingRunner()
    code = main(
        ["run", "--document-folder", str(folder), "--overwrite", *argv_extra],
        runner=r,
    )
    assert code == 0, f"expected success exit, got {code}"
    assert r.invocation is not None
    return r


def test_default_when_no_env_no_flag(
    tmp_document_folder: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    r = _invoke(tmp_document_folder, [])
    assert r.invocation.ollama_url == "http://localhost:11434"


def test_env_used_when_set(
    tmp_document_folder: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-host:11434")
    r = _invoke(tmp_document_folder, [])
    assert r.invocation.ollama_url == "http://env-host:11434"


def test_flag_beats_env(
    tmp_document_folder: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-host:11434")
    r = _invoke(
        tmp_document_folder, ["--ollama-url", "http://flag-host:11434"]
    )
    assert r.invocation.ollama_url == "http://flag-host:11434"


def test_invalid_url_accepted_as_opaque(
    tmp_document_folder: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    r = _invoke(tmp_document_folder, ["--ollama-url", "not-a-url"])
    assert r.invocation.ollama_url == "not-a-url"
