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

from typing import Optional

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
    attach_one_time_gpu_phases,
    build_per_document_failure,
    build_per_document_success,
    emit_run_summary,
)
# Feature 014 / VT-003: `preflight` types are imported lazily inside
# the GPU warm factory. Module-level import would break collection
# for unrelated tests when `preflight.py` is temporarily unavailable
# (T035 collection-time defensive path). The CPU path never references
# preflight.

# Feature 014 (T023 / NEW.4): module-level cache for the
# `PreflightReadout` produced by the inline GPU gate. Set by
# `_maybe_register_warm_preprocess` after a successful classify; read
# by T029 when populating `gpu_init_seconds` in the run summary. The
# variable is process-scoped per Q2 — there is no cross-process cache.
# The annotation uses `Any` here so this module loads without
# preflight.py present; the actual runtime value is a PreflightReadout
# (or None).
_PREFLIGHT_READOUT: Optional[Any] = None

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
    # Feature 014 (Contracts §2 Pre-write GPU gate): warm-corpus GPU
    # preflight failures emit the FR-009 stderr form and exit with the
    # FR-001-state-mapped exit code (10–14) before any artifact write,
    # rather than collapsing to the generic PROCESSING_FAILURE path.
    # Lazy-import the exception types so a missing preflight.py does
    # not break this module at import time (T035 / VT-003).
    try:
        from ledgerlinc_ocr.preprocessing.preflight import (
            GpuPrerequisiteError as _GpuPrerequisiteError,
            exit_code_for_state as _exit_code_for_state,
        )
    except ImportError:
        _GpuPrerequisiteError = None  # type: ignore[assignment]
        _exit_code_for_state = None  # type: ignore[assignment]

    try:
        warm_init_failure = _warm_initialize_live_preprocess(registry, plan)
    except Exception as _exc:  # noqa: BLE001 - intentional: route GPU prereq failures
        if (
            _GpuPrerequisiteError is not None
            and isinstance(_exc, _GpuPrerequisiteError)
            and _exit_code_for_state is not None
        ):
            # FR-009 stderr format: name both selected profile and FR-001 state.
            print(
                f"error: --preprocess-profile=ppstructurev3@gpu: "
                f"{_exc.state.value}; {_exc.recommendation}",
                file=sys.stderr,
            )
            # Emit a partial run_summary so consumers see the abort
            # in the stdout JSON line as well, with the user's
            # requested on_failure preserved verbatim.
            _emit_warm_init_failure_summary(
                documents=documents,
                plan=plan,
                registry=registry,
                message=(
                    f"--preprocess-profile=ppstructurev3@gpu: "
                    f"{_exc.state.value}; {_exc.recommendation}"
                ),
                emit_failure=_emit_failure,
                gpu_prerequisite_failure=True,
            )
            return _exit_code_for_state(_exc.state)
        raise
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
            # Feature 015 (T021 / R-015.4): build the structured
            # phase_timings + per_page_inference blocks that ship in the
            # 0.1.2 schema. Source data: result.timings.stages[PREPROCESS]
            # carries `infer` / `write` (Runner-level) plus the
            # feature-015 fine-grained `rasterization` / `artifact_write`
            # / `total` keys threaded in via the contextvar by the
            # live adapter (stages.py::_ppstructurev3_factory). The
            # per-page inference array drains from the ocr accumulator.
            from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

            preprocess_lane_now = (
                "gpu0" if (
                    plan.profiles.get("preprocess") is not None
                    and plan.profiles["preprocess"].lane == "gpu"
                ) else "cpu"
            )

            # Build phase_timings from the StageTiming map.
            phase_timings: dict[str, dict[str, float]] = {}
            preprocess_st = result.timings.stages.get("preprocess")
            if preprocess_st is not None:
                for phase_key, ns in preprocess_st.phases_ns.items():
                    # Skip the Runner-level coarse keys ("infer", "write")
                    # — they live in the legacy `stages.preprocess` flat
                    # form and the FR-013 phase set is the new canonical
                    # vocabulary. Coarse keys are not in FR-013.
                    if phase_key in {"rasterization", "artifact_write"}:
                        phase_timings[phase_key] = {
                            "seconds": round(ns / 1e9, 6)
                        }
                if preprocess_st.total_ns > 0:
                    phase_timings["total"] = {
                        "seconds": round(preprocess_st.total_ns / 1e9, 6)
                    }

            # Drain per-page inference accumulator. CPU lane always drains
            # (to avoid leaking state) but only attaches on GPU per
            # FR-017 / ISO1.
            _per_page_drained = _ocr_mod.take_gpu_inference_per_page()
            per_page_inference: list[tuple[int, float]] | None = None
            if preprocess_lane_now.startswith("gpu") and _per_page_drained:
                per_page_inference = _per_page_drained

            success_record = build_per_document_success(
                document_id=invocation.document_id,
                folder=folder_raw,
                timings=result.timings,
                phase_timings=phase_timings if phase_timings else None,
                per_page_inference=per_page_inference,
            )
            # Feature 014 (T030): legacy gpu_inference_seconds flat key
            # (sum of per-page seconds) preserved for one schema version.
            if (
                preprocess_lane_now.startswith("gpu")
                and _per_page_drained
            ):
                _gpu_inf = round(sum(s for _, s in _per_page_drained), 6)
                stages_map = success_record.setdefault("stages", {})
                preprocess_stage = stages_map.setdefault(
                    "preprocess", {"total_seconds": 0.0}
                )
                preprocess_stage["gpu_inference_seconds"] = _gpu_inf
            per_document_records.append(success_record)
        else:
            failed += 1
            # Feature 014 (T024 / R-014.4 / FR-010): when the resolved
            # preprocess profile is the GPU lane and a per-document
            # failure surfaces, force-abort the corpus regardless of
            # the user's --on-failure value. The user's requested
            # mode is preserved verbatim in run_summary.on_failure
            # for audit transparency; only the runtime control flow
            # is overridden. The `gpu_lane_forced_abort: true` flag
            # on the per-document failure record signals to consumers
            # that this was a GPU-lane-forced abort, distinct from a
            # user-requested fail-fast.
            preprocess_profile = plan.profiles.get("preprocess")
            is_gpu_lane = (
                preprocess_profile is not None
                and preprocess_profile.implementation == "ppstructurev3"
                and preprocess_profile.lane == "gpu"
            )
            # Attribution: include profile + document_id in the message
            # field so a downstream consumer can identify the failed
            # GPU-profile run (analyze finding VT-010).
            failure_message = result.message
            if is_gpu_lane:
                failure_message = (
                    f"[ppstructurev3@gpu] document_id={invocation.document_id}: "
                    f"{result.message}"
                )
            _emit_failure(
                StructuredFailureRecord.for_code(
                    result.exit_code,
                    stage=result.stage,
                    message=failure_message,
                    artifacts_written=[
                        str(p) for p in result.artifacts_written
                    ],
                )
            )
            # Feature 015 (T023 / Q5 / FP1 / FP2): build partial
            # phase_timings + per_page_inference for the failed doc.
            # Phases that did not run are absent from the dict per FR-016.
            from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

            preprocess_lane_now = "gpu0" if is_gpu_lane else "cpu"
            failure_phase_timings: dict[str, dict[str, float]] = {}
            preprocess_st = result.timings.stages.get("preprocess")
            if preprocess_st is not None:
                for phase_key, ns in preprocess_st.phases_ns.items():
                    if phase_key in {"rasterization", "artifact_write"}:
                        failure_phase_timings[phase_key] = {
                            "seconds": round(ns / 1e9, 6)
                        }
                if preprocess_st.total_ns > 0:
                    failure_phase_timings["total"] = {
                        "seconds": round(preprocess_st.total_ns / 1e9, 6)
                    }

            _failure_per_page_drained = _ocr_mod.take_gpu_inference_per_page()
            failure_per_page: list[tuple[int, float]] | None = None
            if preprocess_lane_now.startswith("gpu") and _failure_per_page_drained:
                failure_per_page = _failure_per_page_drained

            per_document_records.append(
                build_per_document_failure(
                    document_id=invocation.document_id,
                    folder=folder_raw,
                    failed_stage=result.stage,
                    exit_code=int(result.exit_code),
                    message=failure_message,
                    timings=result.timings,
                    gpu_lane_forced_abort=is_gpu_lane,
                    phase_timings=failure_phase_timings if failure_phase_timings else None,
                    per_page_inference=failure_per_page,
                )
            )
            if plan.failure_policy.fail_fast or is_gpu_lane:
                # GPU lane forces abort even when user requested
                # --on-failure=continue (R-014.4). The summary's
                # top-level on_failure field still reports the
                # user-requested mode unchanged.
                break

    registry.close()

    # Feature 014 (T029): resolve the preprocess lane string for the
    # additive `preprocess_lane` field on RunSummary.
    _pp_profile = plan.profiles.get("preprocess")
    if _pp_profile is not None and _pp_profile.lane == "gpu":
        _resolved_preprocess_lane = "gpu0"
    else:
        _resolved_preprocess_lane = "cpu"

    # Feature 014 (T029 / AA4'): if the GPU lane was used and a successful
    # PreflightReadout was cached by T023's warm factory in the
    # module-level `_PREFLIGHT_READOUT` variable, record the one-time
    # PPStructureV3 GPU init time on the FIRST successful per_document
    # entry's preprocess stage as `gpu_init_seconds`. Phase keys absent
    # on subsequent docs per R-009 absence policy. T029 reads the cache
    # set by T023; it MUST NOT re-call classify(...).
    #
    # Feature 015 (T022 / FR-015 / R-015.4): also attach the structured
    # GPU one-time phase keys (paddle_import / gpu_bind_probe /
    # engine_init) to the same first-successful per_document entry's
    # `phase_timings` block. The legacy flat `gpu_init_seconds` is
    # preserved for one schema version of back-compat (FR-014).
    if (
        _resolved_preprocess_lane.startswith("gpu")
        and _PREFLIGHT_READOUT is not None
        and _PREFLIGHT_READOUT.evidence.ppstructurev3_init_seconds is not None
    ):
        _init_seconds = _PREFLIGHT_READOUT.evidence.ppstructurev3_init_seconds
        for record in per_document_records:
            if record.get("status") == "success":
                stages_map = record.setdefault("stages", {})
                preprocess_stage = stages_map.setdefault(
                    "preprocess", {"total_seconds": 0.0}
                )
                preprocess_stage["gpu_init_seconds"] = _init_seconds
                # Feature 015: shared helper attaches structured form
                # (paddle_import / gpu_bind_probe / engine_init) so warm-
                # corpus and single-doc paths stay in sync on field names
                # and None-omission rules.
                attach_one_time_gpu_phases(record, _PREFLIGHT_READOUT)
                break

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
        preprocess_lane=_resolved_preprocess_lane,
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
    gpu_prerequisite_failure: bool = False,
) -> int:
    """Emit the partial run_summary on warm-init failure.

    When `gpu_prerequisite_failure` is True (Contracts §2 Pre-write GPU
    gate), the caller has already emitted the FR-009 stderr form and is
    responsible for the FR-001-state-mapped exit code. This function
    skips the StructuredFailureRecord emission to avoid double-printing
    a stderr line, and it returns ``ExitCode.PROCESSING_FAILURE`` only
    so the legacy CPU/non-GPU code path keeps working — the caller
    discards this return value when ``gpu_prerequisite_failure`` is True.
    """
    first = documents[0]
    if not gpu_prerequisite_failure:
        emit_failure(
            StructuredFailureRecord.for_code(
                ExitCode.PROCESSING_FAILURE,
                stage="preprocess",
                message=message,
            )
        )
    _pp_profile = plan.profiles.get("preprocess")
    _warm_lane = (
        "gpu0" if _pp_profile is not None and _pp_profile.lane == "gpu" else "cpu"
    )
    # Feature 015 (T024 / FP1): on warm-init failure, attach whatever
    # GPU prereq phase timings were captured before the failure (e.g.,
    # `paddle_import` if step 1 ran). Reads from `_PREFLIGHT_READOUT`
    # if it was set by the warm factory before the abort. Field names
    # and None-omission rules come from the shared helper so warm-
    # corpus and single-doc emission cannot drift.
    _warm_init_failure_phase_timings: dict[str, dict[str, float]] = {}
    if _warm_lane.startswith("gpu") and _PREFLIGHT_READOUT is not None:
        _scratch: dict[str, Any] = {}
        attach_one_time_gpu_phases(_scratch, _PREFLIGHT_READOUT)
        _warm_init_failure_phase_timings = _scratch.get("phase_timings", {})

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
        preprocess_lane=_warm_lane,
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
                phase_timings=(
                    _warm_init_failure_phase_timings
                    if _warm_init_failure_phase_timings
                    else None
                ),
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
    # Feature 014 (T023): also accept the GPU lane. The warm factory's
    # initialize() runs the inline preflight gate first via
    # ensure_gpu_ready(), then constructs the singleton with the
    # resolved device. On gate failure GpuPrerequisiteError propagates
    # up and is caught by the existing _warm_initialize_live_preprocess
    # handler, which aborts the run with no per-doc artifacts (FR-009).
    if (profile.implementation, profile.lane) not in {
        ("ppstructurev3", "cpu"),
        ("ppstructurev3", "gpu"),
    }:
        return
    # Capability gate: only warm-init when a real live adapter is registered,
    # not when the test-only stub fallback is in place.
    if not is_live_capable("preprocess", profile.implementation, profile.lane):
        return

    is_gpu_lane = profile.lane == "gpu"
    device_str = "gpu:0" if is_gpu_lane else "cpu"

    class _PPStructureV3WarmInstance:
        def initialize(self) -> None:
            from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

            global _PREFLIGHT_READOUT
            if is_gpu_lane:
                # Feature 014 (T021 / T023 / FR-009): inline GPU gate.
                # Raises GpuPrerequisiteError on any non-success FR-001
                # state; caller (_warm_initialize_live_preprocess) catches
                # the exception and turns it into a run-level abort.
                from ledgerlinc_ocr.preprocessing.preflight import (
                    ensure_gpu_ready as _ensure_gpu_ready,
                )

                _PREFLIGHT_READOUT = _ensure_gpu_ready()
            _ocr_mod._get_engine(device=device_str)  # type: ignore[attr-defined]

        def close(self) -> None:
            return None

    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane=profile.lane,
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
        # Feature 014: GpuPrerequisiteError must propagate so the caller
        # in run_warm_corpus can route it through the FR-009 stderr form
        # and FR-001-state-mapped exit code (Contracts §2 Pre-write GPU
        # gate). Lazy import keeps this module importable when
        # preflight.py is unavailable (T035 / VT-003 defensive scope).
        try:
            from ledgerlinc_ocr.preprocessing.preflight import (
                GpuPrerequisiteError as _GpuPrerequisiteError,
            )
        except ImportError:
            _GpuPrerequisiteError = None  # type: ignore[assignment]
        if (
            _GpuPrerequisiteError is not None
            and isinstance(exc, _GpuPrerequisiteError)
        ):
            raise

        import logging

        message = str(exc) or type(exc).__name__
        logging.getLogger(__name__).warning(
            "warm-preprocess pre-loop initialization raised: %s", message
        )
        return message
    return None


__all__ = ["run_warm_corpus"]
