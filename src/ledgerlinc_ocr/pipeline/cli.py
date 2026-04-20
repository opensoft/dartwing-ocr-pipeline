"""Stage 1 one-document pipeline CLI.

Contract: specs/002-cli-contract/contracts/cli-contract.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ledgerlinc_ocr import __version__ as _package_version
from ledgerlinc_ocr.pipeline.exit_codes import ExitCode, StructuredFailureRecord
from ledgerlinc_ocr.pipeline.path_resolution import (
    PathResolutionError,
    derive_document_id,
    resolve_destination,
    resolve_input_pdf,
)
from ledgerlinc_ocr.pipeline.pdf_check import is_pdf
from ledgerlinc_ocr.pipeline.runner import (
    OFF_LIMITS_NAMES,
    RESERVED_ARTIFACT_NAMES,
    CLIInvocation,
    Runner,
)
from ledgerlinc_ocr.validator.loader import (
    ContractSetNotFoundError,
    load_contract_set,
)

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_POLICY_VERSION = "stage1-baseline-v0"
_DEFAULT_CONTRACT_SET_VERSION = "1.0.0"
_LOG_LEVELS = ("error", "warning", "info", "debug")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ledgerlinc-pipeline",
        description="Stage 1 one-document pipeline CLI",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    run = subparsers.add_parser("run", help="Run pipeline on one PDF")
    run.add_argument("--input", type=Path, default=None)
    run.add_argument("--document-folder", type=Path, default=None)
    run.add_argument("--output-dir", type=Path, default=None)
    run.add_argument("--document-id", type=str, default=None)
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--pipeline-version", type=str, default=_package_version)
    run.add_argument(
        "--policy-version", type=str, default=_DEFAULT_POLICY_VERSION
    )
    run.add_argument(
        "--contract-set-version",
        type=str,
        default=_DEFAULT_CONTRACT_SET_VERSION,
    )
    run.add_argument("--ollama-url", type=str, default=None)
    run.add_argument(
        "--log-level", type=str, choices=list(_LOG_LEVELS), default="warning"
    )
    run.add_argument("--timeout", type=int, default=300)
    return parser


def _emit_failure(record: StructuredFailureRecord) -> None:
    sys.stderr.write(record.as_json_line() + "\n")


def _emit_usage_error(
    message: str, *, help_text: str | None = None
) -> ExitCode:
    if help_text:
        sys.stderr.write(help_text)
        if not help_text.endswith("\n"):
            sys.stderr.write("\n")
    record = StructuredFailureRecord.for_code(
        ExitCode.USAGE_ERROR,
        stage="arguments",
        message=message,
    )
    _emit_failure(record)
    return ExitCode.USAGE_ERROR


def _resolve_ollama_url(flag_value: str | None) -> str:
    if flag_value is not None:
        return flag_value
    env = os.environ.get("OLLAMA_BASE_URL")
    if env:
        return env
    return _DEFAULT_OLLAMA_URL


def _validate_inputs(
    *,
    args: argparse.Namespace,
) -> tuple[ExitCode, str, Path | None, Path | None, str | None]:
    """Resolve and validate inputs.

    Returns (exit_code, message, input_pdf, destination_folder, document_id).
    On USAGE_ERROR, input_pdf / destination_folder / document_id may be None.
    """
    try:
        input_pdf = resolve_input_pdf(args.input, args.document_folder)
    except PathResolutionError as exc:
        return (ExitCode.USAGE_ERROR, str(exc), None, None, None)

    try:
        dest = resolve_destination(
            args.input, args.document_folder, args.output_dir
        )
    except PathResolutionError as exc:
        return (ExitCode.USAGE_ERROR, str(exc), None, None, None)

    document_id = args.document_id or derive_document_id(dest.name)
    if document_id is None:
        return (
            ExitCode.USAGE_ERROR,
            (
                f"cannot derive document_id from folder name {dest.name!r}; "
                f"pass --document-id explicitly"
            ),
            None,
            None,
            None,
        )

    return (ExitCode.SUCCESS, "", input_pdf, dest, document_id)


def _check_filesystem_state(
    *,
    input_pdf: Path,
    dest: Path,
    overwrite: bool,
    document_folder: Path | None,
) -> tuple[ExitCode, str, str]:
    """Return (code, stage, message). SUCCESS => all checks pass."""
    if not input_pdf.exists():
        if document_folder is not None:
            msg = f"Document folder missing source.pdf: {document_folder}"
        else:
            msg = f"Input PDF not found: {input_pdf}"
        return (ExitCode.INPUT_NOT_FOUND, "input_validation", msg)

    if not input_pdf.is_file():
        return (
            ExitCode.INVALID_PDF,
            "input_validation",
            f"Input path is not a regular file: {input_pdf}",
        )

    if not is_pdf(input_pdf):
        return (
            ExitCode.INVALID_PDF,
            "input_validation",
            f"File is not a PDF (magic byte check failed): {input_pdf}",
        )

    if not dest.exists():
        return (
            ExitCode.INPUT_NOT_FOUND,
            "input_validation",
            f"Destination folder does not exist: {dest}",
        )

    if not dest.is_dir():
        return (
            ExitCode.OUTPUT_PATH_NOT_USABLE,
            "input_validation",
            f"Destination is not a directory: {dest}",
        )

    if not os.access(dest, os.W_OK):
        return (
            ExitCode.OUTPUT_PATH_NOT_USABLE,
            "input_validation",
            f"Destination folder is not writable: {dest}",
        )

    if not overwrite:
        for name in RESERVED_ARTIFACT_NAMES:
            existing = dest / name
            if existing.exists():
                return (
                    ExitCode.OUTPUT_IN_USE,
                    "input_validation",
                    (
                        f"Reserved artifact file already exists: {existing}. "
                        f"Pass --overwrite to replace."
                    ),
                )

    return (ExitCode.SUCCESS, "input_validation", "")


def _emit_stdout_summary(
    *, document_id: str, routing_decision: dict, artifacts: list[Path]
) -> None:
    review_status = routing_decision.get("review_status", {})
    payload = {
        "document_id": document_id,
        "decision": routing_decision.get("decision"),
        "manual_review_required": review_status.get(
            "manual_review_required", False
        ),
        "review_reason": review_status.get("review_reason"),
        "artifacts": {
            p.name: str(p)
            for p in artifacts
            if p.name in RESERVED_ARTIFACT_NAMES
        },
    }
    sys.stdout.write(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
    )


def main(argv: list[str] | None = None, *, runner: Runner | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        _emit_failure(
            StructuredFailureRecord.for_code(
                ExitCode.USAGE_ERROR,
                stage="arguments",
                message="invalid arguments",
            )
        )
        return int(ExitCode.USAGE_ERROR)

    if args.subcommand is None:
        return int(
            _emit_usage_error(
                "no subcommand provided; expected 'run'",
                help_text=parser.format_help(),
            )
        )

    try:
        load_contract_set(args.contract_set_version)
    except ContractSetNotFoundError as exc:
        return int(
            _emit_usage_error(
                f"--contract-set-version {args.contract_set_version}: {exc}"
            )
        )

    code, message, input_pdf, dest, document_id = _validate_inputs(args=args)
    if code != ExitCode.SUCCESS:
        return int(_emit_usage_error(message))

    assert input_pdf is not None and dest is not None and document_id is not None

    code, stage, message = _check_filesystem_state(
        input_pdf=input_pdf,
        dest=dest,
        overwrite=args.overwrite,
        document_folder=args.document_folder,
    )
    if code != ExitCode.SUCCESS:
        _emit_failure(
            StructuredFailureRecord.for_code(
                code, stage=stage, message=message
            )
        )
        return int(code)

    invocation = CLIInvocation(
        input_pdf=input_pdf,
        destination_folder=dest,
        document_id=document_id,
        overwrite=args.overwrite,
        pipeline_version=args.pipeline_version,
        policy_version=args.policy_version,
        contract_set_version=args.contract_set_version,
        ollama_url=_resolve_ollama_url(args.ollama_url),
        log_level=args.log_level,
        timeout=args.timeout,
    )

    r = runner if runner is not None else Runner()
    result = r.run(invocation)

    if result.exit_code == ExitCode.SUCCESS:
        assert result.routing_decision is not None
        _emit_stdout_summary(
            document_id=document_id,
            routing_decision=result.routing_decision,
            artifacts=result.artifacts_written,
        )
        return int(ExitCode.SUCCESS)

    _emit_failure(
        StructuredFailureRecord.for_code(
            result.exit_code,
            stage=result.stage,
            message=result.message,
            artifacts_written=[str(p) for p in result.artifacts_written],
        )
    )
    return int(result.exit_code)
