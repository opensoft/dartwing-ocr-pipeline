"""Warm-corpus orchestration loop.

Spec FR-023 / FR-026 / FR-027 / FR-028. Research R-008 / R-009 / R-011.

This module owns the end-to-end loop driven by ``--documents-file``:

  1. Iterate documents in file order (no dedup -- caller's concern).
  2. For each document, build a ``CLIInvocation`` whose
     ``destination_folder`` points at the listed folder, then invoke
     ``Runner.run_plan`` against it.
  3. Capture per-document outcomes (success / failure) and timings.
  4. Honor the ``FailurePolicy`` mode: ``continue`` (default) records the
     failure on stderr and proceeds; ``fail-fast`` stops after the first
     failure.
  5. After the loop, emit the ``kind: "run_summary"`` JSON object on
     stdout as the *last* line (R-009).

The aggregate process exit code follows R-008's severity ordering:
``0`` only when every executed document succeeded; otherwise the
highest-severity per-document exit code observed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable

from ledgerlinc_ocr.pipeline.corpus import DocumentEntry, WarmProfileRegistry
from ledgerlinc_ocr.pipeline.exit_codes import ExitCode, StructuredFailureRecord
from ledgerlinc_ocr.pipeline.path_resolution import derive_document_id
from ledgerlinc_ocr.pipeline.pdf_check import is_pdf
from ledgerlinc_ocr.pipeline.profiles import Stage
from ledgerlinc_ocr.pipeline.runner import (
    CLIInvocation,
    ResolvedRunPlan,
    Runner,
)
from ledgerlinc_ocr.pipeline.stages import is_live_capable
from ledgerlinc_ocr.pipeline.timing import (
    RunSummary,
    build_per_document_failure,
    build_per_document_success,
    emit_run_summary,
)

# Severity ranking per Research R-008. Lower rank == higher severity.
# When aggregating multiple per-document exit codes in continue mode,
# the highest-severity (lowest-rank) code wins.
_SEVERITY_RANK: dict[int, int] = {
    int(ExitCode.PROCESSING_FAILURE): 1,
    int(ExitCode.SCHEMA_VALIDATION_FAILURE): 2,
    int(ExitCode.OUTPUT_PATH_NOT_USABLE): 3,
    int(ExitCode.OUTPUT_IN_USE): 4,
    int(ExitCode.INVALID_PDF): 5,
    int(ExitCode.INPUT_NOT_FOUND): 6,
    int(ExitCode.USAGE_ERROR): 7,
}


def _aggregate_exit_code(observed: list[ExitCode]) -> ExitCode:
    """Return the most-severe non-zero exit code observed, else SUCCESS."""
    non_zero = [c for c in observed if c != ExitCode.SUCCESS]
    if not non_zero:
        return ExitCode.SUCCESS
    # Lowest rank wins (per _SEVERITY_RANK), with INT-fallback ordering
    # so any future code that isn't explicitly ranked still produces
    # a deterministic non-zero outcome.
    return min(
        non_zero,
        key=lambda code: (_SEVERITY_RANK.get(int(code), 99), int(code)),
    )


def _per_document_invocation(
    *,
    base: argparse.Namespace,
    folder: Path,
) -> tuple[CLIInvocation | None, ExitCode | None, str]:
    """Build a CLIInvocation for one document folder.

    Mirrors the cold-path filesystem checks (folder exists + is_dir,
    source.pdf exists + is regular file + magic-byte PDF) so a missing
    or non-PDF source.pdf in warm-corpus mode fails before any artifact
    is written. Without these checks an all-stub default-preprocess
    callable would happily emit success artifacts even when the
    document folder lacks a usable PDF (Copilot review item 2).

    Returns (invocation, error_code, error_message). On success
    error_code is None.
    """
    if not folder.exists():
        return None, ExitCode.INPUT_NOT_FOUND, (
            f"document folder does not exist: {folder}"
        )
    if not folder.is_dir():
        return None, ExitCode.OUTPUT_PATH_NOT_USABLE, (
            f"document path is not a directory: {folder}"
        )
    document_id = derive_document_id(folder.name)
    if document_id is None:
        return None, ExitCode.USAGE_ERROR, (
            f"cannot derive document_id from folder name {folder.name!r}; "
            f"warm-corpus mode requires inv_XXX_<difficulty> folder names"
        )
    pdf_path = folder / "source.pdf"
    if not pdf_path.exists():
        return None, ExitCode.INPUT_NOT_FOUND, (
            f"document folder missing source.pdf: {folder}"
        )
    if not pdf_path.is_file():
        return None, ExitCode.INVALID_PDF, (
            f"source.pdf is not a regular file: {pdf_path}"
        )
    if not is_pdf(pdf_path):
        return None, ExitCode.INVALID_PDF, (
            f"source.pdf failed magic-byte check: {pdf_path}"
        )
    if not os.access(folder, os.W_OK):
        return None, ExitCode.OUTPUT_PATH_NOT_USABLE, (
            f"document folder is not writable: {folder}"
        )
    invocation = CLIInvocation(
        input_pdf=pdf_path,
        destination_folder=folder,
        document_id=document_id,
        overwrite=base.overwrite,
        pipeline_version=base.pipeline_version,
        policy_version=base.policy_version,
        contract_set_version=base.contract_set_version,
        ollama_url=_resolve_gpu_url(base),
        log_level=base.log_level,
        timeout=base.timeout,
        ollama_cpu_url=base.ollama_cpu_url,
        ollama_jetson_url=base.ollama_jetson_url,
    )
    return invocation, None, ""


def _resolve_gpu_url(args: argparse.Namespace) -> str:
    """Mirror cli._resolve_ollama_url without importing it (avoids cycle)."""
    import os
    if args.ollama_url is not None:
        return args.ollama_url
    env = os.environ.get("OLLAMA_BASE_URL")
    if env:
        return env
    return "http://localhost:11434"


def _document_id_for_failure(folder: Path) -> str:
    """Return the best string identifier available for a corpus-validation failure."""
    return derive_document_id(folder.name) or folder.name


def run_warm_corpus(
    *,
    args: argparse.Namespace,
    documents: tuple[DocumentEntry, ...],
    runner: Runner | None,
) -> int:
    """Drive the warm-corpus loop and return the aggregate process exit code.

    ``documents`` is a tuple of ``DocumentEntry`` (raw token + resolved
    Path); the raw token is echoed verbatim into per_document.folder
    while filesystem operations use the resolved absolute path.
    """
    from ledgerlinc_ocr.pipeline.cli import _build_resolved_plan, _emit_failure, _emit_stdout_summary

    # Build a synthetic placeholder invocation purely so plan resolution
    # has a CLIInvocation to attach. Each per-document iteration below
    # rebuilds the plan with the folder-specific CLIInvocation. This
    # decouples the run-summary scaffolding from any per-document
    # validation failures (e.g., bad folder name in documents[0]).
    placeholder_inv = CLIInvocation(
        input_pdf=Path("placeholder/source.pdf"),
        destination_folder=Path("placeholder"),
        document_id="placeholder",
        overwrite=args.overwrite,
        pipeline_version=args.pipeline_version,
        policy_version=args.policy_version,
        contract_set_version=args.contract_set_version,
        ollama_url=_resolve_gpu_url(args),
        log_level=args.log_level,
        timeout=args.timeout,
        ollama_cpu_url=args.ollama_cpu_url,
        ollama_jetson_url=args.ollama_jetson_url,
    )
    resolved_paths = tuple(entry.resolved for entry in documents)
    plan, code, msg = _build_resolved_plan(
        args,
        invocation=placeholder_inv,
        documents=resolved_paths,
        warm_corpus=True,
    )
    if plan is None:
        _emit_failure(
            StructuredFailureRecord.for_code(
                code, stage="arguments", message=msg
            )
        )
        return int(code)

    runner = runner if runner is not None else Runner()
    registry = WarmProfileRegistry.empty()
    _maybe_register_warm_preprocess(registry, plan)
    warm_init_failure = _warm_initialize_live_preprocess(registry, plan)
    if warm_init_failure is not None:
        return _emit_warm_init_failure_summary(
            documents=documents,
            plan=plan,
            registry=registry,
            message=warm_init_failure,
            emit_failure=_emit_failure,
        )

    per_document_records: list[dict[str, Any]] = []
    observed_exit_codes: list[ExitCode] = []
    succeeded = 0
    failed = 0

    for entry in documents:
        folder_raw = entry.raw
        folder_resolved = entry.resolved
        invocation, code, msg = _per_document_invocation(
            base=args, folder=folder_resolved
        )
        if invocation is None:
            failed += 1
            observed_exit_codes.append(code)
            _emit_failure(
                StructuredFailureRecord.for_code(
                    code, stage="corpus_validation", message=msg,
                )
            )
            per_document_records.append(
                build_per_document_failure(
                    document_id=_document_id_for_failure(folder_resolved),
                    folder=folder_raw,
                    failed_stage="corpus_validation",
                    exit_code=int(code),
                    message=msg,
                )
            )
            if plan.failure_policy.fail_fast:
                break
            continue

        # The plan's CLIInvocation reference is the template; per-document
        # we hand ``Runner.run_plan`` the per-folder invocation by
        # rebuilding a plan with cli_invocation replaced. That keeps the
        # plan immutable from one document to the next.
        per_doc_plan = ResolvedRunPlan(
            mode="warm_corpus",
            cli_invocation=invocation,
            profiles=plan.profiles,
            slice_=plan.slice_,
            ollama_endpoints=plan.ollama_endpoints,
            failure_policy=plan.failure_policy,
            stack_preset_name=plan.stack_preset_name,
            documents=plan.documents,
        )

        result = runner.run_plan(per_doc_plan, folder=folder_resolved)
        observed_exit_codes.append(result.exit_code)
        if result.exit_code == ExitCode.SUCCESS:
            succeeded += 1
            _emit_stdout_summary(
                document_id=invocation.document_id,
                routing_decision=result.routing_decision,
                artifacts=result.artifacts_written,
            )
            per_document_records.append(
                build_per_document_success(
                    document_id=invocation.document_id,
                    folder=folder_raw,
                    timings=result.timings,
                )
            )
        else:
            failed += 1
            _emit_failure(
                StructuredFailureRecord.for_code(
                    result.exit_code,
                    stage=result.stage,
                    message=result.message,
                    artifacts_written=[
                        str(p) for p in result.artifacts_written
                    ],
                )
            )
            per_document_records.append(
                build_per_document_failure(
                    document_id=invocation.document_id,
                    folder=folder_raw,
                    failed_stage=result.stage,
                    exit_code=int(result.exit_code),
                    message=result.message,
                    timings=result.timings,
                )
            )
            if plan.failure_policy.fail_fast:
                break

    registry.close()

    summary = RunSummary(
        stack_preset=plan.stack_preset_name,
        resolved_profiles={
            stage: profile.raw_value
            for stage, profile in plan.profiles.items()
        },
        execution_slice={
            "start_at": plan.slice_.start_at,
            "stop_after": plan.slice_.stop_after,
        },
        on_failure=plan.failure_policy.mode,
        documents_total=len(documents),
        documents_succeeded=succeeded,
        documents_failed=failed,
        profile_initialization_seconds=registry.initialization_seconds(),
        per_document=per_document_records,
    )
    emit_run_summary(summary)

    return int(_aggregate_exit_code(observed_exit_codes))


def _emit_warm_init_failure_summary(
    *,
    documents: tuple[DocumentEntry, ...],
    plan: ResolvedRunPlan,
    registry: WarmProfileRegistry,
    message: str,
    emit_failure: Callable[[StructuredFailureRecord], None],
) -> int:
    first = documents[0]
    emit_failure(
        StructuredFailureRecord.for_code(
            ExitCode.PROCESSING_FAILURE,
            stage="preprocess",
            message=message,
        )
    )
    summary = RunSummary(
        stack_preset=plan.stack_preset_name,
        resolved_profiles={
            stage: profile.raw_value
            for stage, profile in plan.profiles.items()
        },
        execution_slice={
            "start_at": plan.slice_.start_at,
            "stop_after": plan.slice_.stop_after,
        },
        on_failure=plan.failure_policy.mode,
        documents_total=len(documents),
        documents_succeeded=0,
        documents_failed=1,
        profile_initialization_seconds=registry.initialization_seconds(),
        per_document=[
            build_per_document_failure(
                document_id=_document_id_for_failure(first.resolved),
                folder=first.raw,
                failed_stage="preprocess",
                exit_code=int(ExitCode.PROCESSING_FAILURE),
                message=message,
            )
        ],
    )
    emit_run_summary(summary)
    registry.close()
    return int(ExitCode.PROCESSING_FAILURE)


def _maybe_register_warm_preprocess(
    registry: WarmProfileRegistry, plan: ResolvedRunPlan
) -> None:
    """Register a warm-instance factory for the live preprocessing profile.

    Fires only when ALL of these hold (Copilot review item 1):
      (a) preprocess is inside the executed slice;
      (b) the selected preprocess profile is live (not stub);
      (c) the live adapter for the (impl, lane) triple is **actually a
          real live adapter**, not a test-only stub-fallback wrapper.
          This is checked via ``stages.is_live_capable``.

    The factory wraps ``preprocessing.ocr._get_engine`` so calling
    ``initialize()`` constructs PPStructureV3 once. SC-009 is honored
    because the upstream module's ``_ENGINE`` global is itself a
    singleton; subsequent per-document calls reuse the warmed engine.
    """
    if "preprocess" not in plan.slice_.stages_in_slice:
        return
    profile = plan.profiles["preprocess"]
    if profile.kind != "live":
        return
    if (profile.implementation, profile.lane) != ("ppstructurev3", "cpu"):
        return
    # Capability gate: only warm-init when a real live adapter is registered,
    # not when the test-only stub fallback is in place.
    if not is_live_capable("preprocess", profile.implementation, profile.lane):
        return

    class _PPStructureV3WarmInstance:
        def initialize(self) -> None:
            from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

            _ocr_mod._get_engine()  # type: ignore[attr-defined]

        def close(self) -> None:
            return None

    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane="cpu",
        factory=_PPStructureV3WarmInstance,
    )


def _warm_initialize_live_preprocess(
    registry: WarmProfileRegistry, plan: ResolvedRunPlan
) -> str | None:
    """If a warm-preprocess factory was registered, trigger initialization
    once before the per-document loop so the run-summary records the
    one-time init cost separately from per-document timings (FR-027).
    """
    if "preprocess" not in plan.slice_.stages_in_slice:
        return None
    profile = plan.profiles["preprocess"]
    if profile.kind != "live":
        return None
    key = ("preprocess", profile.implementation, profile.lane)
    if key not in registry.factories:
        return None
    try:
        registry.get_or_initialize(
            stage="preprocess",
            implementation=profile.implementation,
            lane=profile.lane,
        )
    except Exception as exc:  # noqa: BLE001 -- intentional: see comment
        import logging

        message = str(exc) or type(exc).__name__
        logging.getLogger(__name__).warning(
            "warm-preprocess pre-loop initialization raised: %s", message
        )
        return message
    return None


__all__ = ["run_warm_corpus"]
