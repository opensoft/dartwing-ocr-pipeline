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

from dartwing_ocr.pipeline.corpus import CorpusParseError, parse_documents_file
from dartwing_ocr.pipeline.exit_codes import ExitCode, StructuredFailureRecord
from dartwing_ocr.pipeline.failure_policy import (
    FailurePolicyError,
    parse_on_failure,
)
from dartwing_ocr.pipeline.ollama_lanes import resolve_endpoints
from dartwing_ocr.pipeline.path_resolution import (
    PathResolutionError,
    derive_document_id,
    resolve_destination,
    resolve_input_pdf,
)
from dartwing_ocr.pipeline.pdf_check import is_pdf
from dartwing_ocr.pipeline.profiles import (
    DEFAULT_PROFILES,
    STAGES,
    ProfileValidationError,
    Stage,
    parse_profile,
    resolve_profiles,
)
from dartwing_ocr.pipeline.runner import (
    OFF_LIMITS_NAMES,
    RESERVED_ARTIFACT_NAMES,
    CLIInvocation,
    ResolvedRunPlan,
    Runner,
)
from dartwing_ocr.pipeline.slice_control import SliceError, parse_slice
from dartwing_ocr.preprocessing.evidence_gate_optin import (
    apply_skip_fallback_optin as _apply_evidence_gate_skip_fallback_optin,
)
from dartwing_ocr.preprocessing.warmup_optin import (
    is_warmup_optin_set,
    warn_and_proceed_message,
)
from dartwing_ocr.validator.loader import (
    ContractSetNotFoundError,
    load_contract_set,
)

_DEFAULT_OLLAMA_URL = "http://localhost:11434"
_DEFAULT_POLICY_VERSION = "stage1-baseline-v0"
_DEFAULT_CONTRACT_SET_VERSION = "1.2.0"
_LOG_LEVELS = ("error", "warning", "info", "debug")

_STACK_PRESET_CHOICES = ("full-workstation", "cloud-workstation", "edge-fast")


def _build_parser() -> argparse.ArgumentParser:
    from dartwing_ocr.preprocessing.preprocess_strategies import (
        OCR_ONLY_MIN_CONFIDENCE_MEAN as _OCR_ONLY_MIN_CONFIDENCE_MEAN,
        OCR_ONLY_MIN_TOKEN_COUNT as _OCR_ONLY_MIN_TOKEN_COUNT,
    )
    parser = argparse.ArgumentParser(
        prog="dartwing-pipeline",
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
    # to --preprocess-profile. Also accepted via the DARTWING_GPU_WARMUP=1
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
            "be set via the DARTWING_GPU_WARMUP=1 environment variable; "
            "the CLI flag wins when both are present."
        ),
    )
    # Feature 017 (T009 / T020 / R-017.1 / contracts/cli-contract.md §1):
    # two closed-vocabulary preset axes for the ppstructurev3@gpu lane.
    # Mirrors the preprocess CLI's flags. Resolution happens at argv parse
    # time; UnknownPresetError fails fast with exit code 16 BEFORE any
    # Paddle import. Also accepted via the DARTWING_MODULE_SET and
    # DARTWING_DET_REC_VARIANT environment variables.
    run.add_argument(
        "--module-set",
        type=str,
        default=None,
        help=(
            "Select a named PPStructureV3 module-set preset for "
            "ppstructurev3@gpu. Valid values: legacy, reduced-v1, "
            "cpu-default, stub-default. Defaults to legacy on GPU. "
            "The cpu-default / stub-default identity values are "
            "accepted on non-GPU profiles; any GPU value passed on a "
            "non-GPU profile is ignored with a stderr warning. Can "
            "also be set via DARTWING_MODULE_SET; the CLI flag wins."
        ),
    )
    run.add_argument(
        "--det-rec-variant",
        type=str,
        default=None,
        help=(
            "Select a named detection/recognition model variant for "
            "ppstructurev3@gpu. Valid values: legacy, ppocrv5-mobile, "
            "ppocrv4-mobile, cpu-default, stub-default. Defaults to "
            "legacy on GPU. The cpu-default / stub-default identity "
            "values are accepted on non-GPU profiles; any GPU value "
            "passed on a non-GPU profile is ignored with a stderr "
            "warning. Can also be set via DARTWING_DET_REC_VARIANT."
        ),
    )
    # Feature 018 (T009 / R-018.1 / contracts/cli-contract.md §1):
    # raster-profile axis (DPI). Mirrors the preprocess CLI's flag.
    # Resolution at argv parse time; UnknownPresetError fails fast with
    # exit code 16 BEFORE Paddle import. Also accepted via
    # DARTWING_RASTER_PROFILE env var.
    run.add_argument(
        "--raster-profile",
        type=str,
        default=None,
        help=(
            "Select a named rasterization-DPI preset for "
            "ppstructurev3@gpu. Valid values: legacy, reduced-v1, "
            "cpu-default, stub-default. Defaults to legacy on GPU. "
            "The cpu-default / stub-default identity values are "
            "accepted on non-GPU profiles; any GPU value passed on a "
            "non-GPU profile is ignored with a stderr warning. Can "
            "also be set via DARTWING_RASTER_PROFILE; the CLI flag wins."
        ),
    )
    # Feature 018 (T019 / R-018.4 / contracts/cli-contract.md §1):
    # region-strategy axis (page-area targeting). Mirrors --raster-profile.
    run.add_argument(
        "--region-strategy",
        type=str,
        default=None,
        help=(
            "Select a named region-targeting strategy for "
            "ppstructurev3@gpu. Valid values: full-page, "
            "header-first-v1, cpu-default, stub-default. Defaults to "
            "full-page on GPU. The header-first-v1 strategy processes "
            "only page 1's top-30%% header band; pages 2..N appear as "
            "empty page records. On a no-evidence trigger the strategy "
            "falls back to full-page on that document. Can also be set "
            "via DARTWING_REGION_STRATEGY; the CLI flag wins."
        ),
    )
    # Feature 019 (T009 / R-019.1 / contracts/cli-contract.md §1):
    # preprocess-strategy axis. Mirrors --raster-profile / --region-strategy.
    run.add_argument(
        "--preprocess-strategy",
        type=str,
        default=None,
        help=(
            "Select a named preprocessing-strategy preset for "
            "ppstructurev3@gpu. Valid values: ppstructurev3, "
            "ocr-only-v1. Defaults to "
            "ppstructurev3 on GPU. The ocr-only-v1 strategy invokes "
            "PaddleOCR det+rec only (no layout / table / formula / "
            "seal modules); on the FR-005 combined two-threshold "
            f"trigger (token count < {_OCR_ONLY_MIN_TOKEN_COUNT} OR "
            f"mean confidence < {_OCR_ONLY_MIN_CONFIDENCE_MEAN:.2f}) "
            "falls back to ppstructurev3 on that document and "
            "increments ocr_only_fallback_count. Can also be set via "
            "DARTWING_PREPROCESS_STRATEGY; the CLI flag wins."
        ),
    )
    run.add_argument(
        "--evidence-gate-skip-fallback",
        action="store_true",
        default=False,
        help=(
            "Suppress feature 019's OCR-only-to-PPStructureV3 fallback "
            "when the evidence gate concludes 'sufficient' on the "
            "OCR-only candidate. Off by default. Requires "
            "--preprocess-profile=ppstructurev3@gpu AND "
            "--preprocess-strategy=ocr-only-v1 to have effect. "
            "Warn-and-proceed on non-GPU profiles. Env-var fallback: "
            "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK."
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


def _resolve_warning_profile_name(
    plan_profile: Any, args_preprocess_profile: str | None
) -> str:
    """Resolve the active preprocess-profile name to surface in the FR-010
    warn-and-proceed line. Prefers `plan_profile.raw_value` (reflects
    `--stack-preset` / defaults) over the raw `--preprocess-profile`
    flag the user typed; falls back to the literal default.
    """
    if plan_profile is not None:
        return plan_profile.raw_value
    if args_preprocess_profile:
        return args_preprocess_profile
    return "ppstructurev3@cpu"


def _run_cold_warmup_if_active(invocation: CLIInvocation) -> int | None:
    """Run the hoisted GPU warmup pass for cold mode.

    Returns ``None`` to indicate the runner should proceed; returns an
    integer exit code if warmup failed in a way that aborts the run
    (FR-007 / SC-011 warmup failure → exit 15, or FR-009 GPU-prereq
    failure → exit 10–14). Lazy-imports preprocessing.pipeline so this
    module's import path stays free of PIL / numpy / preprocessing.

    No-op (returns None) when ``invocation.warmup`` is False.
    """
    if not invocation.warmup:
        return None
    from dartwing_ocr.preprocessing.pipeline import (
        run_warmup_if_active as _run_warmup_if_active,
    )
    from dartwing_ocr.preprocessing.errors import WarmupError
    try:
        from dartwing_ocr.preprocessing.preflight import (
            GpuPrerequisiteError as _gpu_prerequisite_error_cls,
            exit_code_for_state as _exit_code_for_state,
        )
    except ImportError:
        _gpu_prerequisite_error_cls = None  # type: ignore[assignment]
        _exit_code_for_state = None  # type: ignore[assignment]
    try:
        # Feature 017 (review CRITICAL fix): forward the resolved preset
        # identifiers so `ensure_gpu_ready` adopts the engine with the
        # operator-selected use_kwargs splat + det/rec model overrides
        # on this first call (cold-path warmup runs BEFORE the runner's
        # stage dispatch; subsequent ensure_gpu_ready calls are cache hits).
        _run_warmup_if_active(
            preprocess_lane="gpu0",  # ppstructurev3@gpu resolves here
            warmup_optin=True,
            module_set_id=invocation.module_set_id,
            det_rec_variant_id=invocation.det_rec_variant_id,
            preprocess_strategy_id=invocation.preprocess_strategy_id,
            evidence_gate_skip_fallback_optin=invocation.evidence_gate_skip_fallback_optin,
        )
    except WarmupError as exc:
        sys.stderr.write(f"error: warmup failed: {exc.cause_class}: {exc}\n")
        return int(ExitCode.WARMUP_FAILED)
    except Exception as exc:  # noqa: BLE001 — route preflight failure
        # `ensure_gpu_ready()` inside `run_warmup_if_active` can raise
        # `GpuPrerequisiteError`. Translate to the FR-009 envelope +
        # FR-001-state-mapped exit code (10–14) per Contracts §1.
        # Any other unexpected exception re-raises.
        if (
            _gpu_prerequisite_error_cls is not None
            and isinstance(exc, _gpu_prerequisite_error_cls)
            and _exit_code_for_state is not None
        ):
            sys.stderr.write(
                f"error: --preprocess-profile=ppstructurev3@gpu: "
                f"{exc.state.value}; {exc.recommendation}\n"
            )
            return int(_exit_code_for_state(exc.state))
        raise
    return None


def _is_legacy_cold_dispatch(args: argparse.Namespace, plan: ResolvedRunPlan) -> bool:
    """Return True iff the cold invocation should use the legacy
    ``runner.run(invocation)`` test seam (no 011 flags supplied)."""
    if plan.stack_preset_name is not None:
        return False
    if plan.slice_.start_at != "preprocess":
        return False
    if plan.slice_.stop_after != "final_payload":
        return False
    return all(
        args_value is None
        for args_value in (
            args.preprocess_profile,
            args.extract_profile,
            args.routing_profile,
            args.final_payload_profile,
            args.start_at,
            args.stop_after,
            args.on_failure,
            args.preprocess_strategy,
            args.ollama_cpu_url,
            args.ollama_jetson_url,
        )
    )


def _emit_cold_result(result: Any, document_id: str) -> int:
    """Convert a cold-mode `RunResult` to the appropriate stdout/stderr
    emission and exit code. Splits success / warmup-failed / generic-
    failure handling out of `_run_cold` to keep its cognitive
    complexity below the SonarCloud threshold.
    """
    if result.exit_code == ExitCode.SUCCESS:
        _emit_stdout_summary(
            document_id=document_id,
            routing_decision=result.routing_decision,
            artifacts=result.artifacts_written,
        )
        return int(ExitCode.SUCCESS)
    # FR-007 / SC-011: warmup failure emits the canonical `error: warmup
    # failed: <cause-class>: <msg>` literal (already shaped by the
    # runner's `_format_stage_exception`) and suppresses the generic
    # StructuredFailureRecord JSON.
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


def _run_cold(  # NOSONAR S3776 — cold-mode CLI orchestrator — splits would fragment the per-stage error-routing contract.
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
    # (`--gpu-warmup` CLI flag + `DARTWING_GPU_WARMUP` env var; CLI wins)
    # and gate it on the resolved preprocess profile lane. On non-GPU
    # profiles emit the FR-010 warn-and-proceed line. `invocation.warmup`
    # is preserved as a CLI-intent flag for diagnostics; runtime warmup
    # is driven by `pipeline.run_warmup_if_active()` below — the hoisted
    # helper that runs OUTSIDE the runner's `measure_total` window per
    # FR-007 / SC-004 (Copilot PR #24 round 2 finding 1).
    _gpu_warmup_optin = is_warmup_optin_set(getattr(args, "gpu_warmup", False))
    _preprocess_in_slice = "preprocess" in plan.slice_.stages_in_slice
    _preprocess_profile = plan.profiles.get("preprocess")
    _preprocess_is_gpu = (
        _preprocess_profile is not None
        and _preprocess_profile.implementation == "ppstructurev3"
        and _preprocess_profile.lane == "gpu"
    )
    if _gpu_warmup_optin and _preprocess_in_slice and not _preprocess_is_gpu:
        sys.stderr.write(
            warn_and_proceed_message(
                _resolve_warning_profile_name(
                    _preprocess_profile, args.preprocess_profile
                )
            )
            + "\n"
        )
    invocation.warmup = (
        _gpu_warmup_optin and _preprocess_in_slice and _preprocess_is_gpu
    )

    # Feature 017 (review HIGH fix): cold-path warn-and-proceed for the
    # two preset axes. Mirrors the warmup_optin block above. When the
    # operator passes a known `--module-set` / `--det-rec-variant` value
    # on a non-GPU profile (CPU or stub), emit one stderr warn line per
    # ignored flag and drop the resolved value (FR-013 / cli-contract.md
    # §3). Unknown values were already rejected at `main()`'s parse-time
    # check (R-017.12 fail-fast → exit 16).
    from dartwing_ocr.preprocessing.preset_optin import (
        resolve_module_set_value as _resolve_module_set_value_017,
        resolve_det_rec_variant_value as _resolve_det_rec_variant_value_017,
        module_set_warn_message as _module_set_warn_017,
        det_rec_variant_warn_message as _det_rec_warn_017,
    )
    _module_set_raw_017 = _resolve_module_set_value_017(getattr(args, "module_set", None))
    _det_rec_raw_017 = _resolve_det_rec_variant_value_017(getattr(args, "det_rec_variant", None))
    if _module_set_raw_017 is not None and _preprocess_in_slice and not _preprocess_is_gpu:
        sys.stderr.write(
            _module_set_warn_017(
                _resolve_warning_profile_name(
                    _preprocess_profile, args.preprocess_profile
                )
            )
            + "\n"
        )
        _module_set_raw_017 = None
    if _det_rec_raw_017 is not None and _preprocess_in_slice and not _preprocess_is_gpu:
        sys.stderr.write(
            _det_rec_warn_017(
                _resolve_warning_profile_name(
                    _preprocess_profile, args.preprocess_profile
                )
            )
            + "\n"
        )
        _det_rec_raw_017 = None
    # Feature 018 (T009 / T019 / R-018.1 / R-018.12 / cli-contract.md §3):
    # raster-profile + region-strategy cold-path warn-and-proceed mirror
    # the feature 017 axes above. Unknown values were already rejected at
    # `main()`'s parse-time check (R-018.12 fail-fast → exit 16).
    from dartwing_ocr.preprocessing.raster_profile_optin import (
        resolve_raster_profile_value as _resolve_raster_profile_value_018,
        raster_profile_warn_message as _raster_profile_warn_018,
    )
    from dartwing_ocr.preprocessing.region_strategy_optin import (
        resolve_region_strategy_value as _resolve_region_strategy_value_018,
        region_strategy_warn_message as _region_strategy_warn_018,
    )
    # Feature 019 (T009 / T028): preprocess-strategy axis cold-path
    # warn-and-proceed mirrors features 017 / 018 axes above.
    from dartwing_ocr.preprocessing.preprocess_strategy_optin import (
        resolve_preprocess_strategy_value as _resolve_preprocess_strategy_value_019,
        preprocess_strategy_warn_message as _preprocess_strategy_warn_019,
    )
    _raster_profile_raw_018 = _resolve_raster_profile_value_018(
        getattr(args, "raster_profile", None)
    )
    _region_strategy_raw_018 = _resolve_region_strategy_value_018(
        getattr(args, "region_strategy", None)
    )
    _preprocess_strategy_raw_019 = _resolve_preprocess_strategy_value_019(
        getattr(args, "preprocess_strategy", None)
    )
    if _raster_profile_raw_018 is not None and _preprocess_in_slice and not _preprocess_is_gpu:
        sys.stderr.write(
            _raster_profile_warn_018(
                _resolve_warning_profile_name(
                    _preprocess_profile, args.preprocess_profile
                )
            )
            + "\n"
        )
        _raster_profile_raw_018 = None
    if _region_strategy_raw_018 is not None and _preprocess_in_slice and not _preprocess_is_gpu:
        sys.stderr.write(
            _region_strategy_warn_018(
                _resolve_warning_profile_name(
                    _preprocess_profile, args.preprocess_profile
                )
            )
            + "\n"
        )
        _region_strategy_raw_018 = None
    if _preprocess_strategy_raw_019 is not None and _preprocess_in_slice and not _preprocess_is_gpu:
        sys.stderr.write(
            _preprocess_strategy_warn_019(
                _resolve_warning_profile_name(
                    _preprocess_profile, args.preprocess_profile
                )
            )
            + "\n"
        )
        _preprocess_strategy_raw_019 = None
    try:
        _evidence_gate_skip_fallback_threaded = _apply_evidence_gate_skip_fallback_optin(
            cli_value=args.evidence_gate_skip_fallback,
            is_gpu_profile=_preprocess_is_gpu,
            active_profile_name=_resolve_warning_profile_name(
                _preprocess_profile, args.preprocess_profile
            ),
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    # Thread the post-warn-and-proceed values onto the cold-path
    # invocation so `_run_inner`'s ensure_gpu_ready call receives them.
    invocation.module_set_id = _module_set_raw_017
    invocation.det_rec_variant_id = _det_rec_raw_017
    invocation.raster_profile_id = _raster_profile_raw_018
    invocation.region_strategy_id = _region_strategy_raw_018
    invocation.preprocess_strategy_id = _preprocess_strategy_raw_019
    invocation.evidence_gate_skip_fallback_optin = _evidence_gate_skip_fallback_threaded

    # Hoisted warmup: must run BEFORE the runner's stage dispatch so
    # warmup duration is excluded from per-doc `phase_timings.total`.
    early_exit = _run_cold_warmup_if_active(invocation)
    if early_exit is not None:
        return early_exit

    r = runner if runner is not None else Runner()
    # In cold mode, call legacy ``runner.run(invocation)`` to preserve the
    # 002-era test seam when no 011 flags are supplied; otherwise route
    # through ``run_plan`` so the configured plan is used.
    if _is_legacy_cold_dispatch(args, plan):
        result = r.run(invocation)
    else:
        result = r.run_plan(plan, folder=dest)

    return _emit_cold_result(result, document_id)


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
    from dartwing_ocr.pipeline.corpus_run import run_warm_corpus

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
    except SystemExit as exc:  # NOSONAR S5754 — intentional: convert argparse's SystemExit into an integer return so library callers (tests, tools) don't see an exception. --help raises SystemExit(0); parse errors raise SystemExit(1+) and are mapped to USAGE_ERROR below.
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

    # Feature 017 (T009 / T020 / R-017.9 / R-017.12) + Feature 018
    # (T009 / R-018.12): validate ALL FOUR preset axes BEFORE any Paddle
    # import. UnknownPresetError fails fast with exit code 16 on any axis.
    # Cross-profile warn-and-proceed (FR-013 / FR-014) is handled in
    # `_run_cold_warmup_if_active` / `corpus_run.py` because those paths
    # know the resolved preprocess lane.
    from dartwing_ocr.preprocessing.preset_optin import (
        resolve_module_set_value as _resolve_module_set_value,
        resolve_det_rec_variant_value as _resolve_det_rec_variant_value,
    )
    from dartwing_ocr.preprocessing.presets import (
        resolve_module_set as _resolve_module_set,
        resolve_det_rec_variant as _resolve_det_rec_variant,
    )
    # Feature 018 (T009 / T019): raster-profile + region-strategy
    # axis resolution at parse time. Same fail-fast contract.
    from dartwing_ocr.preprocessing.raster_profile_optin import (
        resolve_raster_profile_value as _resolve_raster_profile_value,
    )
    from dartwing_ocr.preprocessing.raster_profiles import (
        resolve_raster_profile as _resolve_raster_profile,
    )
    from dartwing_ocr.preprocessing.region_strategy_optin import (
        resolve_region_strategy_value as _resolve_region_strategy_value,
    )
    from dartwing_ocr.preprocessing.region_strategies import (
        resolve_region_strategy as _resolve_region_strategy,
    )
    # Feature 019 (T009): preprocess-strategy parse-time validation
    # mirrors features 017/018 axes above.
    from dartwing_ocr.preprocessing.preprocess_strategy_optin import (
        resolve_preprocess_strategy_value as _resolve_preprocess_strategy_value,
    )
    from dartwing_ocr.preprocessing.preprocess_strategies import (
        resolve_user_preprocess_strategy as _resolve_user_preprocess_strategy,
    )
    from dartwing_ocr.preprocessing.errors import UnknownPresetError as _UnknownPresetError

    _module_set_raw = _resolve_module_set_value(getattr(args, "module_set", None))
    _det_rec_raw = _resolve_det_rec_variant_value(getattr(args, "det_rec_variant", None))
    _raster_profile_raw = _resolve_raster_profile_value(getattr(args, "raster_profile", None))
    _region_strategy_raw = _resolve_region_strategy_value(getattr(args, "region_strategy", None))
    _preprocess_strategy_raw = _resolve_preprocess_strategy_value(
        getattr(args, "preprocess_strategy", None)
    )
    try:
        if _module_set_raw is not None:
            _resolve_module_set(_module_set_raw)
        if _det_rec_raw is not None:
            _resolve_det_rec_variant(_det_rec_raw)
        if _raster_profile_raw is not None:
            _resolve_raster_profile(_raster_profile_raw)
        if _region_strategy_raw is not None:
            _resolve_region_strategy(_region_strategy_raw)
        if _preprocess_strategy_raw is not None:
            _resolve_user_preprocess_strategy(_preprocess_strategy_raw)
    except _UnknownPresetError as exc:
        valid_str = ", ".join(exc.valid_values)
        sys.stderr.write(
            f"error: unknown {exc.preset_axis}: {exc.preset_value!r} — "
            f"valid values are: {valid_str}\n"
        )
        return int(exc.exit_code)

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
