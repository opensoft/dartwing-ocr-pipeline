"""Harness-side invocation of the public pipeline CLI.

The evaluator intentionally does not import ``dartwing_ocr.pipeline``.
Pipeline preparation is a subprocess boundary so the harness exercises the
same controller surface operators use while preserving the constitution's
runtime separation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


_STUB_PROFILE_ARGS: tuple[str, ...] = (
    "--preprocess-profile",
    "stub",
    "--extract-profile",
    "stub",
    "--routing-profile",
    "stub",
    "--final-payload-profile",
    "stub",
)


@dataclass(frozen=True, slots=True)
class PipelinePreparationRequest:
    target: str
    path: Path
    contract_set_version: str
    overwrite: bool = False
    stack_preset: str | None = None
    preprocess_profile: str | None = None
    extract_profile: str | None = None
    routing_profile: str | None = None
    final_payload_profile: str | None = None
    start_at: str | None = None
    stop_after: str | None = None
    ollama_url: str | None = None
    ollama_cpu_url: str | None = None
    ollama_jetson_url: str | None = None
    timeout: int | None = None
    on_failure: str | None = None

    @property
    def uses_stub_defaults(self) -> bool:
        return all(
            value is None
            for value in (
                self.stack_preset,
                self.preprocess_profile,
                self.extract_profile,
                self.routing_profile,
                self.final_payload_profile,
            )
        )


@dataclass(frozen=True, slots=True)
class PreparedDocumentFailure:
    document_id: str
    folder: str
    failed_stage: str | None
    exit_code: int | None
    message: str | None


@dataclass(frozen=True, slots=True)
class PipelinePreparationOutcome:
    return_code: int
    stdout: str
    stderr: str
    command: tuple[str, ...]
    run_summary: dict[str, object] | None = None
    prepared_folders: tuple[Path, ...] = ()
    failed_documents: tuple[PreparedDocumentFailure, ...] = ()

    @property
    def ok(self) -> bool:
        return self.return_code == 0


def build_pipeline_command(
    request: PipelinePreparationRequest,
    *,
    documents_file: Path | None = None,
) -> tuple[str, ...]:
    """Build the pipeline subprocess argv without shell expansion."""
    argv: list[str] = [
        sys.executable,
        "-m",
        "dartwing_ocr.pipeline",
        "run",
    ]
    if request.target == "document":
        argv.extend(["--document-folder", str(request.path)])
    elif request.target == "corpus":
        if documents_file is None:
            raise ValueError("documents_file is required for corpus preparation")
        argv.extend(["--documents-file", str(documents_file)])
        if request.on_failure:
            argv.extend(["--on-failure", request.on_failure])
    else:
        raise ValueError(f"unsupported pipeline preparation target: {request.target}")

    argv.extend(["--contract-set-version", request.contract_set_version])
    if request.overwrite:
        argv.append("--overwrite")

    if request.uses_stub_defaults:
        argv.extend(_STUB_PROFILE_ARGS)
    else:
        _extend_optional(argv, "--stack-preset", request.stack_preset)
        _extend_optional(argv, "--preprocess-profile", request.preprocess_profile)
        _extend_optional(argv, "--extract-profile", request.extract_profile)
        _extend_optional(argv, "--routing-profile", request.routing_profile)
        _extend_optional(
            argv, "--final-payload-profile", request.final_payload_profile
        )

    _extend_optional(argv, "--start-at", request.start_at)
    _extend_optional(argv, "--stop-after", request.stop_after)
    _extend_optional(argv, "--ollama-url", request.ollama_url)
    _extend_optional(argv, "--ollama-cpu-url", request.ollama_cpu_url)
    _extend_optional(argv, "--ollama-jetson-url", request.ollama_jetson_url)
    if request.timeout is not None:
        argv.extend(["--timeout", str(request.timeout)])
    return tuple(argv)


def run_document_preparation(
    request: PipelinePreparationRequest,
) -> PipelinePreparationOutcome:
    command = build_pipeline_command(request)
    completed = subprocess.run(command, capture_output=True, text=True)
    prepared = (request.path,) if completed.returncode == 0 else ()
    return PipelinePreparationOutcome(
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=command,
        prepared_folders=prepared,
    )


def run_corpus_preparation(
    request: PipelinePreparationRequest,
    document_folders: Sequence[Path],
) -> PipelinePreparationOutcome:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="dartwing-eval-docs-", suffix=".txt"
    ) as fh:
        for folder in document_folders:
            fh.write(str(Path(folder).resolve()) + "\n")
        fh.flush()
        documents_file = Path(fh.name)
        command = build_pipeline_command(request, documents_file=documents_file)
        completed = subprocess.run(command, capture_output=True, text=True)

    summary = parse_pipeline_run_summary(completed.stdout)
    prepared = _prepared_folders_from_summary(summary)
    failed = _failed_documents_from_summary(summary)
    return PipelinePreparationOutcome(
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=command,
        run_summary=summary,
        prepared_folders=prepared,
        failed_documents=failed,
    )


def parse_pipeline_run_summary(stdout: str) -> dict[str, object] | None:
    """Return the final pipeline ``kind: run_summary`` object when present."""
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("kind") == "run_summary":
            return payload
    return None


def format_preparation_error(outcome: PipelinePreparationOutcome) -> str:
    lines = [
        f"pipeline preparation failed with exit code {outcome.return_code}",
    ]
    if outcome.stderr.strip():
        lines.append(outcome.stderr.strip())
    elif outcome.stdout.strip():
        lines.append(outcome.stdout.strip())
    return "\n".join(lines)


def format_corpus_preparation_report(
    outcome: PipelinePreparationOutcome,
) -> str:
    summary = outcome.run_summary or {}
    total = summary.get("documents_total", len(outcome.prepared_folders))
    succeeded = summary.get("documents_succeeded", len(outcome.prepared_folders))
    failed = summary.get("documents_failed", len(outcome.failed_documents))
    lines = [
        (
            "pipeline preparation: "
            f"total={total} succeeded={succeeded} failed={failed} "
            f"exit_code={outcome.return_code}"
        )
    ]
    init = summary.get("profile_initialization_seconds")
    if isinstance(init, dict) and init:
        parts = [f"{key}={value}s" for key, value in sorted(init.items())]
        lines.append("pipeline warm initialization: " + ", ".join(parts))
    for failure in outcome.failed_documents:
        message = failure.message or "pipeline preparation failed"
        stage = failure.failed_stage or "unknown"
        lines.append(
            f"pipeline preparation failed: {failure.document_id} "
            f"stage={stage} exit_code={failure.exit_code} message={message}"
        )
    if outcome.stderr.strip():
        lines.append(outcome.stderr.strip())
    return "\n".join(lines)


def _extend_optional(
    argv: list[str], flag: str, value: str | None
) -> None:
    if value is not None:
        argv.extend([flag, value])


def _prepared_folders_from_summary(
    summary: dict[str, object] | None,
) -> tuple[Path, ...]:
    if not summary:
        return ()
    records = summary.get("per_document")
    if not isinstance(records, list):
        return ()
    folders: list[Path] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("status") != "success":
            continue
        folder = record.get("folder")
        if isinstance(folder, str) and folder:
            folders.append(Path(folder))
    return tuple(folders)


def _failed_documents_from_summary(
    summary: dict[str, object] | None,
) -> tuple[PreparedDocumentFailure, ...]:
    if not summary:
        return ()
    records = summary.get("per_document")
    if not isinstance(records, list):
        return ()
    failures: list[PreparedDocumentFailure] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("status") != "failure":
            continue
        failures.append(
            PreparedDocumentFailure(
                document_id=str(record.get("document_id") or ""),
                folder=str(record.get("folder") or ""),
                failed_stage=_optional_str(record.get("failed_stage")),
                exit_code=_optional_int(record.get("exit_code")),
                message=_optional_str(record.get("message")),
            )
        )
    return tuple(failures)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None
