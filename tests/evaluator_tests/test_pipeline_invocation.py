"""012 harness pipeline invocation unit tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ledgerlinc_ocr.evaluator.pipeline_invocation import (
    PipelinePreparationRequest,
    build_pipeline_command,
    format_corpus_preparation_report,
    parse_pipeline_run_summary,
    run_corpus_preparation,
)


def test_build_document_command_uses_stub_profiles_by_default(tmp_path: Path) -> None:
    request = PipelinePreparationRequest(
        target="document",
        path=tmp_path / "inv_001_easy",
        contract_set_version="1.1.0",
    )

    command = build_pipeline_command(request)

    assert command[:4] == (
        sys.executable,
        "-m",
        "ledgerlinc_ocr.pipeline",
        "run",
    )
    assert "--document-folder" in command
    assert "--stack-preset" not in command
    for flag in (
        "--preprocess-profile",
        "--extract-profile",
        "--routing-profile",
        "--final-payload-profile",
    ):
        index = command.index(flag)
        assert command[index + 1] == "stub"


def test_build_document_command_preserves_explicit_stack_and_profiles(
    tmp_path: Path,
) -> None:
    request = PipelinePreparationRequest(
        target="document",
        path=tmp_path / "inv_001_easy",
        contract_set_version="1.1.0",
        overwrite=True,
        stack_preset="full-workstation",
        extract_profile="ollama@cpu",
        ollama_cpu_url="https://ollama-cpu.example.invalid",
        timeout=30,
    )

    command = build_pipeline_command(request)

    assert "--overwrite" in command
    assert "--stack-preset" in command
    assert command[command.index("--stack-preset") + 1] == "full-workstation"
    assert command[command.index("--extract-profile") + 1] == "ollama@cpu"
    assert "--preprocess-profile" not in command
    assert command[command.index("--ollama-cpu-url") + 1] == (
        "https://ollama-cpu.example.invalid"
    )
    assert command[command.index("--timeout") + 1] == "30"


def test_empty_profile_string_is_passed_to_pipeline_for_rejection(
    tmp_path: Path,
) -> None:
    request = PipelinePreparationRequest(
        target="document",
        path=tmp_path / "inv_001_easy",
        contract_set_version="1.1.0",
        extract_profile="",
    )

    command = build_pipeline_command(request)

    assert "--preprocess-profile" not in command
    assert command[command.index("--extract-profile") + 1] == ""


def test_parse_pipeline_run_summary_returns_last_summary_line() -> None:
    stdout = "\n".join(
        [
            json.dumps({"document_id": "inv_001"}),
            "not json",
            json.dumps(
                {
                    "kind": "run_summary",
                    "documents_total": 1,
                    "documents_succeeded": 1,
                    "documents_failed": 0,
                    "profile_initialization_seconds": {},
                    "per_document": [],
                }
            ),
        ]
    )

    summary = parse_pipeline_run_summary(stdout)

    assert summary is not None
    assert summary["documents_total"] == 1


def test_run_corpus_preparation_parses_successes_and_failures(monkeypatch) -> None:
    summary = {
        "kind": "run_summary",
        "documents_total": 2,
        "documents_succeeded": 1,
        "documents_failed": 1,
        "profile_initialization_seconds": {"preprocess": 1.25},
        "per_document": [
            {
                "document_id": "inv_001",
                "folder": "build/evaluator/inv_001_easy",
                "status": "success",
            },
            {
                "document_id": "inv_002",
                "folder": "build/evaluator/inv_002_easy",
                "status": "failure",
                "failed_stage": "preprocess",
                "exit_code": 11,
                "message": "missing source.pdf",
            },
        ],
    }

    def fake_run(command, *, capture_output, text):
        assert capture_output is True
        assert text is True
        assert "--documents-file" in command
        return subprocess.CompletedProcess(
            command,
            returncode=11,
            stdout=json.dumps(summary) + "\n",
            stderr="",
        )

    monkeypatch.setattr(
        "ledgerlinc_ocr.evaluator.pipeline_invocation.subprocess.run",
        fake_run,
    )
    request = PipelinePreparationRequest(
        target="corpus",
        path=Path("build/evaluator/corpus"),
        contract_set_version="1.1.0",
        on_failure="continue",
    )

    outcome = run_corpus_preparation(
        request,
        [
            Path("build/evaluator/inv_001_easy"),
            Path("build/evaluator/inv_002_easy"),
        ],
    )

    assert outcome.return_code == 11
    assert outcome.prepared_folders == (Path("build/evaluator/inv_001_easy"),)
    assert len(outcome.failed_documents) == 1
    assert outcome.failed_documents[0].failed_stage == "preprocess"
    report = format_corpus_preparation_report(outcome)
    assert "total=2 succeeded=1 failed=1" in report
    assert "preprocess=1.25s" in report
