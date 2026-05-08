"""Stage 1 pipeline CLI.

Contract (amended): specs/011-stage-runtime-profiles/contracts/cli-contract.md
(supersedes specs/002-cli-contract/contracts/cli-contract.md v1.0.0).

The CLI accepts:
  - one of ``--input`` / ``--document-folder`` / ``--documents-file``
    (cold single-document vs. warm-corpus mode);
  - per-stage profile flags (``--preprocess-profile`` etc.) and the
    ``--stack-preset`` convenience expansion;
  - execution slicing (``--start-at`` / ``--stop-after``);
  - per-lane Ollama URL overrides (``--ollama-url`` / ``--ollama-cpu-url``
    / ``--ollama-jetson-url``);
  - the warm-corpus failure policy (``--on-failure``).

The four canonical artifact filenames and the per-document stdout/stderr
record shapes are preserved verbatim from the frozen 002 surface (FR-002
/ FR-029).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from ledgerlinc_ocr.pipeline.corpus import CorpusParseError, parse_documents_file
from ledgerlinc_ocr.pipeline.exit_codes import ExitCode, StructuredFailureRecord
from ledgerlinc_ocr.pipeline.failure_policy import (
    FailurePolicyError,
    parse_on_failure,
)
from ledgerlinc_ocr.pipeline.ollama_lanes import resolve_endpoints
from ledgerlinc_ocr.pipeline.path_resolution import (
    PathResolutionError,
    derive_document_id,
    resolve_destination,
    resolve_input_pdf,
)
from ledgerlinc_ocr.pipeline.pdf_check import is_pdf
from ledgerlinc_ocr.pipeline.profiles import (
    DEFAULT_PROFILES,
    STAGES,
    ProfileValidationError,
    Stage,
    parse_profile,
    resolve_profiles,
)
from ledgerlinc_ocr.pipeline.runner import (
    OFF_LIMITS_NAMES,
    RESERVED_ARTIFACT_NAMES,
    CLIInvocation,
    ResolvedRunPlan,
    Runner,
)
from ledgerlinc_ocr.pipeline.slice_control import SliceError, parse_slice
from ledgerlinc_ocr.preprocessing.warmup_optin import (
    is_warmup_optin_set,
    warn_and_proceed_message,
)
from ledgerlinc_ocr.validator.loader import (
    ContractSetNotFoundError,
    load_contract_set,
)

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_POLICY_VERSION = "stage1-baseline-v0"
_DEFAULT_CONTRACT_SET_VERSION = "1.2.0"
_LOG_LEVELS = ("error", "warning", "info", "debug")

_STACK_PRESET_CHOICES = ("full-workstation", "cloud-workstation", "edge-fast")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ledgerlinc-pipeline",
        description="Stage 1 pipeline CLI (single-document or warm corpus)",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    run = subparsers.add_parser("run", help="Run the pipeline")
    # Input selectors (mutually exclusive; checked after parse).
    run.add_argument("--input", type=Path, default=None)
    run.add_argument("--document-folder", type=Path, default=None)
    run.add_argument("--documents-file", type=Path, default=None)

    run.add_argument("--output-dir", type=Path, default=None)
    run.add_argument("--document-id", type=str, default=None)
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--pipeline-version", type=str, default=None)
    run.add_argument(
        "--policy-version", type=str, default=_DEFAULT_POLICY_VERSION
    )
    run.add_argument(
        "--contract-set-version",
        type=str,
        default=_DEFAULT_CONTRACT_SET_VERSION,
    )
    # Per-stage profile flags (FR-003).
    run.add_argument("--preprocess-profile", type=str, default=None)
    run.add_argument("--extract-profile", type=str, default=None)
    run.add_argument("--routing-profile", type=str, default=None)
    run.add_argument("--final-payload-profile", type=str, default=None)
    # Feature 016 (T009 / FR-002 / R-016.1 / contracts/cli-contract.md §1):
    # opt-in GPU warmup pass for ppstructurev3@gpu. Off by default; orthogonal
    # to --preprocess-profile. Also accepted via the LEDGERLINC_GPU_WARMUP=1
    # env var (CLI flag wins when both set). On non-GPU profiles emits the
    # FR-010 warn-and-proceed line and is otherwise a no-op.
    run.add_argument(
        "--gpu-warmup",
        action="store_true",
        default=False,
        help=(
            "Run a one-time PPStructureV3 warmup pass after engine "
            "construction so MIOpen/COMGR kernel-selection cost is paid up "
            "front. Reported as phase_timings.warmup on the first successful "
            "per-document run_summary entry. Has no effect on non-GPU "
            "profiles (a stderr warning is emitted in that case). Can also "
            "be set via the LEDGERLINC_GPU_WARMUP=1 environment variable; "
            "the CLI flag wins when both are present."
        ),
    )
    # Stack preset (FR-004A).
    run.add_argument(
        "--stack-preset",
        type=str,
        default=None,
        choices=list(_STACK_PRESET_CHOICES),
    )
    # Execution slice (FR-004).
    run.add_argument(
        "--start-at",
        type=str,
        default=None,
        choices=list(STAGES),
    )
    run.add_argument(
        "--stop-after",
        type=str,
        default=None,
        choices=list(STAGES),
    )
    # Failure policy (FR-028). No argparse choices: case-insensitive /
    # whitespace-tolerant parsing is owned by ``parse_on_failure`` in
    # ``failure_policy.py`` so spellings like ``Continue`` / ``FAIL-FAST``
    # are accepted per the 011 contract and unit tests.
    run.add_argument(
        "--on-failure",
        type=str,
        default=None,
    )
    # Ollama lane URL overrides (FR-015 / FR-016 / FR-017).
    run.add_argument("--ollama-url", type=str, default=None)
    run.add_argument("--ollama-cpu-url", type=str, default=None)
    run.add_argument("--ollama-jetson-url", type=str, default=None)
    run.add_argument(
        "--log-level", type=str, choices=list(_LOG_LEVELS), default="warning"
    )
    run.add_argument("--timeout", type=int, default=300)
    return parser


def _emit_failure(record: StructuredFailureRecord) -> None:
    sys.stderr.write(record.as_json_line() + "\n")


def _emit_usage_error(
    message: str,
    *,
    help_text: str | None = None,
    stage: str = "arguments",
) -> ExitCode:
    if help_text:
        sys.stderr.write(help_text)
        if not help_text.endswith("\n"):
            sys.stderr.write("\n")
    record = StructuredFailureRecord.for_code(
        ExitCode.USAGE_ERROR,
        stage=stage,
        message=message,
    )
    _emit_failure(record)
    return ExitCode.USAGE_ERROR


def _check_input_selector_exclusive(
    args: argparse.Namespace,
) -> str | None:
    """Return None if exactly one selector is set; otherwise an error message."""
    selectors = [
        ("--input", args.input is not None),
        ("--document-folder", args.document_folder is not None),
        ("--documents-file", args.documents_file is not None),
    ]
    chosen = [name for name, present in selectors if present]
    if len(chosen) == 0:
        return (
            "exactly one of --input / --document-folder / --documents-file "
            "is required"
        )
    if len(chosen) > 1:
        return (
            "exactly one of --input / --document-folder / --documents-file "
            f"is allowed (got: {', '.join(chosen)})"
        )
    return None


def _emit_stdout_summary(
    *,
    document_id: str,
    routing_decision: dict | None,
    artifacts: list[Path],
    stream: Any = None,
) -> None:
    """Emit the per-document 002-shape success record on stdout (no kind field)."""
    target = stream if stream is not None else sys.stdout
    decision = None
    review_status: dict[str, Any] = {}
    if routing_decision is not None:
        decision = routing_decision.get("decision")
        review_status = routing_decision.get("review_status", {})
    payload = {
        "document_id": document_id,
        "decision": decision,
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
    target.write(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
    )


def _build_resolved_plan(
    args: argparse.Namespace,
    *,
    invocation: CLIInvocation,
    documents: tuple[Path, ...],
    warm_corpus: bool,
) -> tuple[ResolvedRunPlan | None, ExitCode | None, str]:
    """Resolve profiles, slice, lanes, failure policy into a ResolvedRunPlan.

    Returns (plan, error_code, error_message). On success, error_code is
    None. On failure, plan is None and error_code/message describe what
    to emit on stderr.
    """
    # Profile resolution.
    explicit: dict[Stage, str | None] = {
        "preprocess": args.preprocess_profile,
        "extract": args.extract_profile,
        "routing": args.routing_profile,
        "final_payload": args.final_payload_profile,
    }
    try:
        profiles, preset_name = resolve_profiles(
            stack_preset=args.stack_preset, explicit=explicit
        )
    except ProfileValidationError as exc:
        return None, ExitCode.USAGE_ERROR, str(exc)

    # Slice resolution.
    try:
        exec_slice = parse_slice(
            start_at=args.start_at, stop_after=args.stop_after
        )
    except SliceError as exc:
        return None, ExitCode.USAGE_ERROR, str(exc)

    # Lane URL resolution.
    endpoints = resolve_endpoints(
        gpu_flag=args.ollama_url,
        cpu_flag=args.ollama_cpu_url,
        jetson_flag=args.ollama_jetson_url,
    )

    # Failure policy.
    try:
        failure_policy = parse_on_failure(
            args.on_failure, warm_corpus=warm_corpus
        )
    except FailurePolicyError as exc:
        return None, ExitCode.USAGE_ERROR, str(exc)

    plan = ResolvedRunPlan(
        mode="warm_corpus" if warm_corpus else "cold_single_document",
        cli_invocation=invocation,
        profiles=profiles,
        slice_=exec_slice,
        ollama_endpoints=endpoints,
        failure_policy=failure_policy,
        stack_preset_name=preset_name,
        documents=documents,
    )
    return plan, None, ""


def _run_cold(
    args: argparse.Namespace, runner: Runner | None
) -> int:
    """Cold single-document path (--input or --document-folder)."""
    try:
        input_pdf = resolve_input_pdf(args.input, args.document_folder)
    except PathResolutionError as exc:
        return int(_emit_usage_error(str(exc)))
    try:
        dest = resolve_destination(
            args.input, args.document_folder, args.output_dir
        )
    except PathResolutionError as exc:
        return int(_emit_usage_error(str(exc)))
    document_id = args.document_id or derive_document_id(dest.name)
    if document_id is None:
        return int(_emit_usage_error(
            f"cannot derive document_id from folder name {dest.name!r}; "
            f"pass --document-id explicitly"
        ))

    code, stage, message = _check_filesystem_state(
        input_pdf=input_pdf,
        dest=dest,
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
        ollama_cpu_url=args.ollama_cpu_url,
        ollama_jetson_url=args.ollama_jetson_url,
    )

    plan, code, message = _build_resolved_plan(
        args,
        invocation=invocation,
        documents=(dest,),
        warm_corpus=False,
    )
    if plan is None:
        return int(_emit_usage_error(message))

    # Feature 016: cold-mode warmup wiring. Resolve the activation surface
    # (`--gpu-warmup` CLI flag + `LEDGERLINC_GPU_WARMUP` env var; CLI wins)
    # and gate it on the resolved preprocess profile lane. On non-GPU
    # profiles emit the FR-010 warn-and-proceed line. `invocation.warmup`
    # is preserved as a CLI-intent flag for diagnostics; runtime warmup
    # is driven by `pipeline.run_warmup_if_active()` below — the hoisted
    # helper that runs OUTSIDE the runner's `measure_total` window per
    # FR-007 / SC-004 (Copilot PR #24 round 2 finding 1).
    _gpu_warmup_optin = is_warmup_optin_set(getattr(args, "gpu_warmup", False))
    _preprocess_profile = plan.profiles.get("preprocess")
    _preprocess_is_gpu = (
        _preprocess_profile is not None
        and _preprocess_profile.implementation == "ppstructurev3"
        and _preprocess_profile.lane == "gpu"
    )
    if _gpu_warmup_optin and not _preprocess_is_gpu:
        # Source the warning's profile name from the resolved plan so it
        # reflects the active profile after stack-preset / defaults
        # resolution, not only the raw `--preprocess-profile` flag the
        # user typed (Copilot PR #24 round 4).
        if _preprocess_profile is not None:
            _profile_name_for_warning = _preprocess_profile.raw_value
        elif args.preprocess_profile:
            _profile_name_for_warning = args.preprocess_profile
        else:
            _profile_name_for_warning = "ppstructurev3@cpu"
        sys.stderr.write(
            warn_and_proceed_message(_profile_name_for_warning) + "\n"
        )
    invocation.warmup = _gpu_warmup_optin and _preprocess_is_gpu

    # Hoisted warmup: must run BEFORE the runner's stage dispatch so
    # warmup duration is excluded from per-doc `phase_timings.total`.
    # Lazy-import the helper + exception types so this module's import
    # path stays free of `preprocessing.pipeline` (which transitively
    # pulls in PIL/numpy) and a missing preflight.py does not break
    # collection.
    if invocation.warmup:
        from ledgerlinc_ocr.preprocessing.pipeline import (
            run_warmup_if_active as _run_warmup_if_active,
        )
        from ledgerlinc_ocr.preprocessing.errors import WarmupError
        try:
            from ledgerlinc_ocr.preprocessing.preflight import (
                GpuPrerequisiteError as _GpuPrerequisiteError,
                exit_code_for_state as _exit_code_for_state,
            )
        except ImportError:
            _GpuPrerequisiteError = None  # type: ignore[assignment]
            _exit_code_for_state = None  # type: ignore[assignment]
        try:
            _run_warmup_if_active(
                preprocess_lane="gpu0",  # ppstructurev3@gpu resolves here
                warmup_optin=True,
            )
        except WarmupError as exc:
            sys.stderr.write(
                f"error: warmup failed: {exc.cause_class}: {exc}\n"
            )
            return int(ExitCode.WARMUP_FAILED)
        except Exception as _exc:  # noqa: BLE001 — route preflight failure
            # `ensure_gpu_ready()` inside `run_warmup_if_active` can raise
            # `GpuPrerequisiteError`. Translate to the FR-009 envelope +
            # FR-001-state-mapped exit code (10–14) per Contracts §1,
            # mirroring the warm-corpus path's pre-write GPU gate
            # (`pipeline/corpus_run.py` ~L240). Any other unexpected
            # exception re-raises (back-compat: prior behavior on the
            # cold-path warmup-disabled flow lets exceptions surface).
            if (
                _GpuPrerequisiteError is not None
                and isinstance(_exc, _GpuPrerequisiteError)
                and _exit_code_for_state is not None
            ):
                sys.stderr.write(
                    f"error: --preprocess-profile=ppstructurev3@gpu: "
                    f"{_exc.state.value}; {_exc.recommendation}\n"
                )
                return int(_exit_code_for_state(_exc.state))
            raise

    r = runner if runner is not None else Runner()
    # In cold mode, call legacy ``runner.run(invocation)`` to preserve the
    # 002-era test seam. ``Runner.run`` internally builds a default plan
    # and delegates to ``run_plan`` -- but if the caller passed any 011
    # flag (profile / slice / preset / lane / on-failure), the plan we
    # just built reflects that, so we route through ``run_plan`` for
    # those cases.
    legacy_args = (
        plan.stack_preset_name is None
        and plan.slice_.start_at == "preprocess"
        and plan.slice_.stop_after == "final_payload"
        and all(
            args_value is None
            for args_value in (
                args.preprocess_profile,
                args.extract_profile,
                args.routing_profile,
                args.final_payload_profile,
                args.start_at,
                args.stop_after,
                args.on_failure,
                args.ollama_cpu_url,
                args.ollama_jetson_url,
            )
        )
    )
    if legacy_args:
        result = r.run(invocation)
    else:
        result = r.run_plan(plan, folder=dest)

    if result.exit_code == ExitCode.SUCCESS:
        _emit_stdout_summary(
            document_id=document_id,
            routing_decision=result.routing_decision,
            artifacts=result.artifacts_written,
        )
        return int(ExitCode.SUCCESS)

    # Feature 016 / FR-007 / SC-011 / cli-contract.md §3-§4: warmup
    # failures emit the canonical `error: warmup failed: <cause-class>:
    # <message>` literal stderr line and exit 15 with NO
    # StructuredFailureRecord JSON. `result.message` is already shaped
    # by `_format_stage_exception` to `warmup failed: <cause>: <msg>`,
    # so the `error: ` prefix is added here.
    if result.exit_code == ExitCode.WARMUP_FAILED:
        sys.stderr.write(f"error: {result.message}\n")
        return int(result.exit_code)

    _emit_failure(
        StructuredFailureRecord.for_code(
            result.exit_code,
            stage=result.stage,
            message=result.message,
            artifacts_written=[str(p) for p in result.artifacts_written],
        )
    )
    return int(result.exit_code)


def _run_warm_corpus(
    args: argparse.Namespace, runner: Runner | None
) -> int:
    """Warm-corpus path (--documents-file). Implemented in US6 phase (T029-T032)."""
    # Reject flags that don't apply in warm-corpus mode (per Contract
    # "Mutual exclusion / ordering rules").
    if args.output_dir is not None:
        return int(_emit_usage_error(
            "--output-dir is not allowed with --documents-file; warm "
            "corpus runs always write into each listed document folder"
        ))
    if args.document_id is not None:
        return int(_emit_usage_error(
            "--document-id is not allowed with --documents-file; document "
            "ids are derived per-folder"
        ))

    # Parse the documents-file into DocumentEntry pairs (raw token +
    # resolved Path). The warm-corpus orchestration loop preserves
    # entry.raw verbatim in per_document.folder so callers using
    # relative corpus paths can correlate the run-summary back to the
    # source file (Copilot review item 3).
    from ledgerlinc_ocr.pipeline.corpus_run import run_warm_corpus

    try:
        entries = parse_documents_file(args.documents_file)
    except CorpusParseError as exc:
        return int(_emit_usage_error(str(exc), stage="corpus_validation"))

    return run_warm_corpus(
        args=args,
        documents=tuple(entries),
        runner=runner,
    )


def _resolve_ollama_url(flag_value: str | None) -> str:
    """Resolve the GPU lane URL for the cold-mode CLIInvocation field."""
    if flag_value is not None:
        return flag_value
    env = os.environ.get("OLLAMA_BASE_URL")
    if env:
        return env
    return _DEFAULT_OLLAMA_URL


def _check_filesystem_state(
    *,
    input_pdf: Path,
    dest: Path,
    document_folder: Path | None,
) -> tuple[ExitCode, str, str]:
    """Validate cold-mode filesystem state. Slice-scoped overwrite is enforced
    in ``Runner.run_plan`` once the plan is resolved (FR-011 / R-006).
    """
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

    return (ExitCode.SUCCESS, "input_validation", "")


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

    # Mutual exclusion check across all three input selectors.
    err = _check_input_selector_exclusive(args)
    if err is not None:
        return int(_emit_usage_error(err))

    try:
        load_contract_set(args.contract_set_version)
    except ContractSetNotFoundError as exc:
        return int(
            _emit_usage_error(
                f"--contract-set-version {args.contract_set_version}: {exc}"
            )
        )

    if args.documents_file is not None:
        return _run_warm_corpus(args, runner)
    return _run_cold(args, runner)


__all__ = ["_DEFAULT_CONTRACT_SET_VERSION", "main"]
