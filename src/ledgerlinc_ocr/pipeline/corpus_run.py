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
from typing import Any, Callable, Optional

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
from ledgerlinc_ocr.preprocessing.errors import WarmupError
from ledgerlinc_ocr.preprocessing.warmup_optin import (
    is_gpu_lane,
    is_warmup_optin_set,
    warn_and_proceed_message,
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
    module_set_id: str | None = None,
    det_rec_variant_id: str | None = None,
    raster_profile_id: str | None = None,
    region_strategy_id: str | None = None,
    preprocess_strategy_id: str | None = None,
    evidence_gate_skip_fallback_optin: bool = False,
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
        module_set_id=module_set_id,
        det_rec_variant_id=det_rec_variant_id,
        raster_profile_id=raster_profile_id,
        region_strategy_id=region_strategy_id,
        preprocess_strategy_id=preprocess_strategy_id,
        evidence_gate_skip_fallback_optin=evidence_gate_skip_fallback_optin,
    )
    return invocation, None, ""


def _resolve_gpu_url(args: argparse.Namespace) -> str:
    """Mirror cli._resolve_ollama_url without importing it (avoids cycle)."""
    if args.ollama_url is not None:
        return args.ollama_url
    env = os.environ.get("OLLAMA_BASE_URL")
    if env:
        return env
    return "http://localhost:11434"


def _document_id_for_failure(folder: Path) -> str:
    """Return the best string identifier available for a corpus-validation failure."""
    return derive_document_id(folder.name) or folder.name


def run_warm_corpus(  # NOSONAR - legacy orchestrator; behavior-preserving split pending
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

    # Feature 017 (review CRITICAL fix): resolve the two preset axes
    # for the warm-corpus path BEFORE registering the warm factory so
    # `ensure_gpu_ready(module_set=..., det_rec_variant=...)` receives
    # the resolved values on the first-and-only `classify(...)` call
    # (R-017.6 / preflight.py:ensure_gpu_ready). Cross-profile
    # warn-and-proceed (FR-013) is also applied here for the warm
    # corpus path — previously this branch was missing (review HIGH).
    # Unknown values were already rejected at `pipeline/cli.py::main`
    # before reaching this point (R-017.12 fail-fast).
    from ledgerlinc_ocr.preprocessing.preset_optin import (
        resolve_module_set_value as _resolve_module_set_value_017,
        resolve_det_rec_variant_value as _resolve_det_rec_variant_value_017,
        is_gpu_lane as _is_gpu_lane_017,
        module_set_warn_message as _module_set_warn_017,
        det_rec_variant_warn_message as _det_rec_warn_017,
    )

    _module_set_raw_017 = _resolve_module_set_value_017(getattr(args, "module_set", None))
    _det_rec_raw_017 = _resolve_det_rec_variant_value_017(getattr(args, "det_rec_variant", None))
    # Feature 018 (T009 / T010 / T019 / T020 / R-018.1 / R-018.4):
    # raster-profile + region-strategy axis resolution mirrors feature
    # 017's two axes above. Same parse-order, same cross-profile
    # warn-and-proceed (FR-014).
    from ledgerlinc_ocr.preprocessing.raster_profile_optin import (
        resolve_raster_profile_value as _resolve_raster_profile_value_018,
        raster_profile_warn_message as _raster_profile_warn_018,
    )
    from ledgerlinc_ocr.preprocessing.region_strategy_optin import (
        resolve_region_strategy_value as _resolve_region_strategy_value_018,
        region_strategy_warn_message as _region_strategy_warn_018,
    )
    from ledgerlinc_ocr.preprocessing.evidence_gate_optin import (
        apply_skip_fallback_optin as _apply_evidence_gate_skip_fallback_optin,
    )
    from ledgerlinc_ocr.preprocessing.preprocess_strategy_optin import (
        resolve_preprocess_strategy_value as _resolve_preprocess_strategy_value_019,
        preprocess_strategy_warn_message as _preprocess_strategy_warn_019,
    )
    _raster_profile_raw_018 = _resolve_raster_profile_value_018(
        getattr(args, "raster_profile", None)
    )
    _region_strategy_raw_018 = _resolve_region_strategy_value_018(
        getattr(args, "region_strategy", None)
    )
    _module_set_threaded_017: str | None = _module_set_raw_017
    _det_rec_threaded_017: str | None = _det_rec_raw_017
    _raster_profile_threaded_018: str | None = _raster_profile_raw_018
    _region_strategy_threaded_018: str | None = _region_strategy_raw_018
    # Feature 019 (T006a / T009 / T010 / T028): preprocess-strategy axis
    # raw CLI value + threading variable. The CLI flag `--preprocess-strategy`
    # is registered in T009 (US1) and threaded through here; the
    # warn-and-proceed nulling on CPU/stub mirrors features 017/018's
    # existing nulling pattern.
    _preprocess_strategy_raw_019 = _resolve_preprocess_strategy_value_019(
        getattr(args, "preprocess_strategy", None)
    )
    _preprocess_strategy_threaded_019: str | None = _preprocess_strategy_raw_019
    _warm_pp_profile_017 = plan.profiles.get("preprocess")
    _warm_lane_017 = (
        "gpu0"
        if _warm_pp_profile_017 is not None
        and _warm_pp_profile_017.implementation == "ppstructurev3"
        and _warm_pp_profile_017.lane == "gpu"
        else "cpu"
    )
    _preprocess_in_slice_for_warn_017 = "preprocess" in plan.slice_.stages_in_slice
    if _preprocess_in_slice_for_warn_017 and not _is_gpu_lane_017(_warm_lane_017):
        _profile_for_warn_017 = (
            _warm_pp_profile_017.raw_value
            if _warm_pp_profile_017 is not None
            else (getattr(args, "preprocess_profile", None) or "ppstructurev3@cpu")
        )
        if _module_set_raw_017 is not None:
            sys.stderr.write(_module_set_warn_017(_profile_for_warn_017) + "\n")
            _module_set_threaded_017 = None
        if _det_rec_raw_017 is not None:
            sys.stderr.write(_det_rec_warn_017(_profile_for_warn_017) + "\n")
            _det_rec_threaded_017 = None
        if _raster_profile_raw_018 is not None:
            sys.stderr.write(_raster_profile_warn_018(_profile_for_warn_017) + "\n")
            _raster_profile_threaded_018 = None
        if _region_strategy_raw_018 is not None:
            sys.stderr.write(_region_strategy_warn_018(_profile_for_warn_017) + "\n")
            _region_strategy_threaded_018 = None
        if _preprocess_strategy_raw_019 is not None:
            sys.stderr.write(_preprocess_strategy_warn_019(_profile_for_warn_017) + "\n")
            _preprocess_strategy_threaded_019 = None

    try:
        _evidence_gate_skip_fallback_threaded = _apply_evidence_gate_skip_fallback_optin(
            cli_value=args.evidence_gate_skip_fallback,
            is_gpu_profile=_is_gpu_lane_017(_warm_lane_017),
            active_profile_name=(
                _warm_pp_profile_017.raw_value
                if _warm_pp_profile_017 is not None
                else (getattr(args, "preprocess_profile", None) or "ppstructurev3@cpu")
            ),
        )
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    # Resolve the threaded values to preset objects for the warm-init factory.
    _module_set_obj_017: object | None = None
    _det_rec_variant_obj_017: object | None = None
    if _is_gpu_lane_017(_warm_lane_017):
        from ledgerlinc_ocr.preprocessing.presets import (
            resolve_module_set as _resolve_module_set_017,
            resolve_det_rec_variant as _resolve_det_rec_variant_017,
        )
        if _module_set_threaded_017 is not None:
            _module_set_obj_017 = _resolve_module_set_017(_module_set_threaded_017)
        if _det_rec_threaded_017 is not None:
            _det_rec_variant_obj_017 = _resolve_det_rec_variant_017(_det_rec_threaded_017)

    runner = runner if runner is not None else Runner()
    registry = WarmProfileRegistry.empty()
    _maybe_register_warm_preprocess(
        registry,
        plan,
        module_set=_module_set_obj_017,
        det_rec_variant=_det_rec_variant_obj_017,
        preprocess_strategy_threaded=_preprocess_strategy_threaded_019,
    )
    # Feature 014 (Contracts §2 Pre-write GPU gate): warm-corpus GPU
    # preflight failures emit the FR-009 stderr form and exit with the
    # FR-001-state-mapped exit code (10–14) before any artifact write,
    # rather than collapsing to the generic PROCESSING_FAILURE path.
    # Lazy-import the exception types so a missing preflight.py does
    # not break this module at import time (T035 / VT-003).
    try:
        from ledgerlinc_ocr.preprocessing.preflight import (
            GpuPrerequisiteError as _gpu_prerequisite_error_type,
            exit_code_for_state as _exit_code_for_state,
        )
    except ImportError:
        _gpu_prerequisite_error_type = None  # type: ignore[assignment]
        _exit_code_for_state = None  # type: ignore[assignment]

    try:
        warm_init_failure = _warm_initialize_live_preprocess(registry, plan)
    except Exception as _exc:  # noqa: BLE001 - intentional: route GPU prereq failures
        if (
            _gpu_prerequisite_error_type is not None
            and isinstance(_exc, _gpu_prerequisite_error_type)
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
                module_set_threaded=_module_set_threaded_017,
                det_rec_variant_threaded=_det_rec_threaded_017,
                preprocess_strategy_threaded=_preprocess_strategy_threaded_019,
                raster_profile_threaded=_raster_profile_threaded_018,
                region_strategy_threaded=_region_strategy_threaded_018,
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
            module_set_threaded=_module_set_threaded_017,
            det_rec_variant_threaded=_det_rec_threaded_017,
            raster_profile_threaded=_raster_profile_threaded_018,
            region_strategy_threaded=_region_strategy_threaded_018,
            preprocess_strategy_threaded=_preprocess_strategy_threaded_019,
        )

    # Feature 016 (T007 / R-016.10 / FR-001 / FR-007 / SC-011): the warm
    # corpus warmup hook fires AFTER `_warm_initialize_live_preprocess`
    # succeeded and BEFORE the per-document loop opens any
    # `measure_total`/`measure_phase` block. Per Clarifications Q3 /
    # R-019.16, `_warm_initialize_live_preprocess` adopts the PPStructureV3
    # singleton via `ocr._adopt_engine` when
    # `preprocess_strategy_id != "ocr-only-v1"` (i.e., the default
    # PPStructureV3 path); on `--preprocess-strategy=ocr-only-v1` it
    # constructs the OCR-only PaddleOCR singleton via
    # `ocr_only._get_ocr_engine` and leaves PPStructureV3 unconstructed.
    # The activation surface mirrors the single-doc path: CLI flag
    # `--gpu-warmup` plus env var `LEDGERLINC_GPU_WARMUP=1` (CLI wins).
    # On non-GPU profiles we emit the FR-010 warn-and-proceed line and
    # skip the warmup invocation. When preprocess is outside the executed
    # slice, warmup is also skipped because no engine was initialized for
    # this run. On WarmupError we exit 15 with stderr
    # `error: warmup failed: <cause>` and emit NO run_summary at all
    # (SC-011 (c)).
    _gpu_warmup_optin = is_warmup_optin_set(getattr(args, "gpu_warmup", False))
    _preprocess_profile_raw = getattr(args, "preprocess_profile", None)
    _preprocess_in_slice = "preprocess" in plan.slice_.stages_in_slice
    # Resolve the plan's preprocess profile to the same lane-string form the
    # single-doc CLI uses ("cpu" / "gpu0") so the activation check goes
    # through `is_gpu_lane()` — single source of truth shared with
    # preprocessing/cli.py per warmup_optin.is_gpu_lane.
    _warm_preprocess_profile = plan.profiles.get("preprocess")
    _warmup_lane = (
        "gpu0"
        if (
            _warm_preprocess_profile is not None
            and _warm_preprocess_profile.implementation == "ppstructurev3"
            and _warm_preprocess_profile.lane == "gpu"
        )
        else "cpu"
    )
    _is_gpu_warmup_active = (
        _gpu_warmup_optin and _preprocess_in_slice and is_gpu_lane(_warmup_lane)
    )
    if _gpu_warmup_optin and _preprocess_in_slice and not _is_gpu_warmup_active:
        # Warn-and-proceed: opt-in set but profile is not ppstructurev3@gpu.
        # Source the warning's profile name from the resolved plan
        # (`plan.profiles["preprocess"].raw_value`) so it reflects the
        # active profile after stack-preset / defaults resolution, not
        # only the raw `--preprocess-profile` flag the user typed
        # (Copilot PR #24 round 4).
        if _warm_preprocess_profile is not None:
            _profile_name_for_warning = _warm_preprocess_profile.raw_value
        elif _preprocess_profile_raw:
            _profile_name_for_warning = _preprocess_profile_raw
        else:
            _profile_name_for_warning = "ppstructurev3@cpu"
        print(warn_and_proceed_message(_profile_name_for_warning), file=sys.stderr)
    if _is_gpu_warmup_active:
        try:
            from ledgerlinc_ocr.preprocessing import warmup as _warmup_mod
            from ledgerlinc_ocr.preprocessing.preprocess_strategies import (
                resolve_preprocess_strategy as _resolve_preprocess_strategy_019,
            )

            _is_ocr_only_warmup = (
                _preprocess_strategy_threaded_019 is not None
                and _resolve_preprocess_strategy_019(
                    _preprocess_strategy_threaded_019
                ).kind == "ocr-only"
            )
            if _is_ocr_only_warmup:
                from ledgerlinc_ocr.preprocessing import ocr_only as _ocr_only_mod

                _warmup_mod.run_warmup(_ocr_only_mod.get_active_ocr_engine())
            else:
                from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

                _warmup_mod.run_warmup(_ocr_mod.get_active_engine())
        except WarmupError as _warmup_exc:
            print(
                f"error: warmup failed: {_warmup_exc.cause_class}: {_warmup_exc}",
                file=sys.stderr,
            )
            # Per SC-011: no run_summary is emitted on warmup failure.
            # Use the canonical ExitCode enum (single source of truth) per
            # Copilot review: avoids drift with the duplicate
            # `EXIT_WARMUP_FAILED` symbol in `preprocessing.errors`.
            return int(ExitCode.WARMUP_FAILED)

    per_document_records: list[dict[str, Any]] = []
    observed_exit_codes: list[ExitCode] = []
    succeeded = 0
    failed = 0
    _region_strategy_fallback_count_018 = 0
    # Feature 019 (T006a / T022): per-doc OCR-only fallback accumulator.
    # Incremented by 1 per document whose `--preprocess-strategy=ocr-only-v1`
    # output fails the FR-005 combined two-threshold eligibility check and
    # falls back to `ppstructurev3` on that document (I-019.4 per-document
    # granularity). US3's wiring (T021) sets `Invocation.ocr_only_fallback_fired`;
    # this loop aggregates the flag the same way feature 018 does for
    # `region_strategy_fallback_fired`.
    _ocr_only_fallback_count_019 = 0
    # Per-doc evidence-gate accumulators. The gate runs on the FINAL
    # preprocess_output.json of each successful document and contributes
    # one record to `documents` plus an increment to `state_counts[decision]`.
    # Per MI-18: `state_counts[s]` equals `count(documents[i].decision == s)`.
    _evidence_gate_state_counts: dict[str, int] = {
        "sufficient": 0,
        "borderline": 0,
        "insufficient": 0,
    }
    _evidence_gate_documents: list[dict[str, Any]] = []
    _evidence_gate_suppressed_fallback_count = 0

    for entry in documents:
        folder_raw = entry.raw
        folder_resolved = entry.resolved
        invocation, code, msg = _per_document_invocation(
            base=args,
            folder=folder_resolved,
            module_set_id=_module_set_threaded_017,
            det_rec_variant_id=_det_rec_threaded_017,
            raster_profile_id=_raster_profile_threaded_018,
            region_strategy_id=_region_strategy_threaded_018,
            preprocess_strategy_id=_preprocess_strategy_threaded_019,
            evidence_gate_skip_fallback_optin=_evidence_gate_skip_fallback_threaded,
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
        if invocation.region_strategy_fallback_fired:
            _region_strategy_fallback_count_018 += 1
        # Feature 019 (T006a / T022): aggregate per-doc OCR-only fallback
        # flag. The live preprocessing adapter (T021) copies the per-document
        # `preprocessing.pipeline.Invocation.ocr_only_fallback_fired` flag
        # back onto this warm-corpus `CLIInvocation` exactly like feature
        # 018 does for `region_strategy_fallback_fired`.
        if getattr(invocation, "ocr_only_fallback_fired", False):
            _ocr_only_fallback_count_019 += 1
        observed_exit_codes.append(result.exit_code)
        if (
            result.exit_code == ExitCode.SUCCESS
            and invocation.evidence_gate_suppressed_fired
        ):
            _evidence_gate_suppressed_fallback_count += 1
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
            # Feature 020 (T028 / R-020.7 / R-020.10 / R-020.11 / FR-003 /
            # FR-006): evaluate the evidence gate on the FINAL
            # preprocess_output.json of this successful document. The
            # decision is recorded against the file as it actually
            # landed on disk (post-fallback if fallback fired per
            # feature 019). The gate is a pure read over
            # preprocess_output content — no Paddle, no GPU, runs on
            # CPU profiles + stub adapters uniformly per FR-014.
            try:
                from ledgerlinc_ocr.preprocessing.evidence_gate import (
                    build_evidence_gate_document_record,
                    evaluate_evidence_gate,
                    load_preprocess_output_for_gate,
                )

                _gate_input = load_preprocess_output_for_gate(
                    folder_resolved / "preprocess_output.json"
                )
                if _gate_input is not None:
                    _gate_result = evaluate_evidence_gate(_gate_input)
                    _evidence_gate_state_counts[_gate_result.decision] += 1
                    _evidence_gate_documents.append(
                        build_evidence_gate_document_record(
                            document_id=invocation.document_id,
                            result=_gate_result,
                        )
                    )
                # If the file cannot be loaded (missing / malformed),
                # the gate skips this document — counters stay where
                # they are. This is a conservative miss; the document
                # is already counted in `documents_succeeded` so the
                # discrepancy is auditable (state_counts sum can be
                # less than documents_succeeded when artifact writes
                # raced). In normal operation every successful
                # document has a readable preprocess_output.json.
            except Exception:  # noqa: BLE001 — gate failure must not break the run
                # Defensive: a bug in the gate module MUST NOT abort
                # the corpus run. The gate is observability — its
                # failure surfaces as missing per-doc records in
                # `evidence_gate_documents`, which the always-emit
                # contract on the four `run_summary` fields still
                # honors (default-zero counters + empty array).
                pass
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
            preprocess_is_gpu = (
                preprocess_profile is not None
                and preprocess_profile.implementation == "ppstructurev3"
                and preprocess_profile.lane == "gpu"
            )
            # Attribution: include profile + document_id in the message
            # field so a downstream consumer can identify the failed
            # GPU-profile run (analyze finding VT-010).
            failure_message = result.message
            if preprocess_is_gpu:
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

            preprocess_lane_now = "gpu0" if preprocess_is_gpu else "cpu"
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
                    gpu_lane_forced_abort=preprocess_is_gpu,
                    phase_timings=failure_phase_timings if failure_phase_timings else None,
                    per_page_inference=failure_per_page,
                )
            )
            if plan.failure_policy.fail_fast or preprocess_is_gpu:
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
        # Feature 016 (T007 / R-016.8 / contracts/module-invariants.md I-11):
        # if warmup ran successfully on this process, capture the cached
        # seconds so the same first-successful-doc record carries the
        # additive `phase_timings.warmup` key alongside `paddle_import` /
        # `gpu_bind_probe` / `engine_init`. The four first-doc one-time
        # GPU phases form a coherent set per I-11.
        _warmup_seconds_for_attach: float | None = None
        if _is_gpu_warmup_active:
            from ledgerlinc_ocr.preprocessing import warmup as _warmup_mod
            _warmup_seconds_for_attach = _warmup_mod.get_cached_warmup_seconds()
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
                # Feature 016: also attach `warmup` (or omit if None).
                attach_one_time_gpu_phases(
                    record,
                    _PREFLIGHT_READOUT,
                    warmup_seconds=_warmup_seconds_for_attach,
                )
                break

    from ledgerlinc_ocr.preprocessing.preset_optin import (
        derive_run_summary_identifiers as _derive_identifiers_017,
    )
    _module_set_id_017, _det_rec_variant_id_017 = _derive_identifiers_017(
        threaded_module_set=_module_set_threaded_017,
        threaded_det_rec_variant=_det_rec_threaded_017,
        preprocess_lane=_resolved_preprocess_lane,
    )
    # Feature 018 (T020 / R-018.8 / Clarifications Q4): per-doc fallback
    # accumulator. The live preprocessing adapter copies the per-document
    # `preprocessing.pipeline.Invocation.region_strategy_fallback_fired`
    # flag back onto this warm-corpus `CLIInvocation`; aggregate it once
    # per document after `runner.run_plan()` returns.
    # Feature 018 (T010 / T020 / R-018.1 / R-018.4): derive
    # raster_profile_id and region_strategy_id for the run_summary using
    # the same threading logic as feature 017's two axes.
    from ledgerlinc_ocr.preprocessing.raster_profile_optin import (
        derive_run_summary_raster_profile_id as _derive_raster_profile_id_018,
    )
    from ledgerlinc_ocr.preprocessing.region_strategy_optin import (
        derive_run_summary_region_strategy_id as _derive_region_strategy_id_018,
    )
    _raster_profile_id_018 = _derive_raster_profile_id_018(
        threaded_raster_profile=_raster_profile_threaded_018,
        preprocess_lane=_resolved_preprocess_lane,
    )
    _region_strategy_id_018 = _derive_region_strategy_id_018(
        threaded_region_strategy=_region_strategy_threaded_018,
        preprocess_lane=_resolved_preprocess_lane,
    )
    # Feature 019 (T006a / T011 / R-019.1 / R-019.4): derive
    # preprocess_strategy_id for the run_summary using the same threading
    # logic as feature 017/018 axes. T011 (US1 wiring) plumbs the CLI/env
    # value into `_preprocess_strategy_threaded_019` upstream; the warn-
    # and-proceed CPU/stub nulling lands in T028 (US4). At Phase 2 there
    # is no CLI flag yet, so `_preprocess_strategy_threaded_019` is None
    # and the helper falls through to the GPU/CPU lane default
    # (LEGACY_PREPROCESS_STRATEGY on GPU; CPU_DEFAULT_PREPROCESS_STRATEGY
    # on CPU).
    from ledgerlinc_ocr.preprocessing.preprocess_strategy_optin import (
        derive_run_summary_preprocess_strategy_id as _derive_preprocess_strategy_id_019,
    )
    _preprocess_strategy_id_019 = _derive_preprocess_strategy_id_019(
        threaded_preprocess_strategy=_preprocess_strategy_threaded_019,
        preprocess_lane=_resolved_preprocess_lane,
    )
    if _pp_profile is not None and _pp_profile.kind == "stub":
        from ledgerlinc_ocr.preprocessing.identifiers import (
            STUB_DEFAULT_DET_REC_VARIANT,
            STUB_DEFAULT_MODULE_SET,
            STUB_DEFAULT_PREPROCESS_STRATEGY,
            STUB_DEFAULT_RASTER_PROFILE,
            STUB_DEFAULT_REGION_STRATEGY,
        )

        _module_set_id_017 = STUB_DEFAULT_MODULE_SET
        _det_rec_variant_id_017 = STUB_DEFAULT_DET_REC_VARIANT
        _raster_profile_id_018 = STUB_DEFAULT_RASTER_PROFILE
        _region_strategy_id_018 = STUB_DEFAULT_REGION_STRATEGY
        # Feature 019 (T006a / US4): stub adapter uses stub-default
        # discrimination for the preprocess-strategy axis as well.
        _preprocess_strategy_id_019 = STUB_DEFAULT_PREPROCESS_STRATEGY
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
        module_set_id=_module_set_id_017,
        det_rec_variant_id=_det_rec_variant_id_017,
        # ppstructure_modules_invoked left at default `[]` until T010's
        # GPU audit-callable invocation lands (deferred per FR-024).
        # Feature 018 (T010 / T020 / R-018.1 / R-018.4 / R-018.8):
        # all three additive top-level fields wired. raster_profile_id
        # and region_strategy_id derived via derive_*; the per-doc
        # `region_strategy_fallback_fired` flag is set per-document by
        # `_run_inner` after the orchestrator's region-first path and is
        # aggregated above immediately after each per-document run.
        raster_profile_id=_raster_profile_id_018,
        region_strategy_id=_region_strategy_id_018,
        region_strategy_fallback_count=_region_strategy_fallback_count_018,
        # Feature 019 (T006a / T011 / T022 / R-019.14): two additive
        # top-level fields. preprocess_strategy_id derived via derive_*;
        # ocr_only_fallback_count is the per-doc accumulator above
        # (increments per fallen-back document per I-019.4).
        preprocess_strategy_id=_preprocess_strategy_id_019,
        ocr_only_fallback_count=_ocr_only_fallback_count_019,
        evidence_gate_id="v1",
        evidence_gate_state_counts=_evidence_gate_state_counts,
        evidence_gate_documents=_evidence_gate_documents,
        evidence_gate_suppressed_fallback_count=_evidence_gate_suppressed_fallback_count,
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
    module_set_threaded: str | None = None,
    det_rec_variant_threaded: str | None = None,
    raster_profile_threaded: str | None = None,
    region_strategy_threaded: str | None = None,
    preprocess_strategy_threaded: str | None = None,
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

    from ledgerlinc_ocr.preprocessing.preset_optin import (
        derive_run_summary_identifiers as _derive_identifiers_017,
    )
    _failure_module_set_id, _failure_det_rec_variant_id = _derive_identifiers_017(
        threaded_module_set=module_set_threaded,
        threaded_det_rec_variant=det_rec_variant_threaded,
        preprocess_lane=_warm_lane,
    )
    # Feature 018 (T010 / T020 / R-018.1 / R-018.4): raster-profile +
    # region-strategy axes on warm-init failure path mirror the feature
    # 017 axes above.
    from ledgerlinc_ocr.preprocessing.raster_profile_optin import (
        derive_run_summary_raster_profile_id as _derive_raster_profile_id_018,
    )
    from ledgerlinc_ocr.preprocessing.region_strategy_optin import (
        derive_run_summary_region_strategy_id as _derive_region_strategy_id_018,
    )
    _failure_raster_profile_id = _derive_raster_profile_id_018(
        threaded_raster_profile=raster_profile_threaded,
        preprocess_lane=_warm_lane,
    )
    _failure_region_strategy_id = _derive_region_strategy_id_018(
        threaded_region_strategy=region_strategy_threaded,
        preprocess_lane=_warm_lane,
    )
    # Feature 019 (T006a / T011 / R-019.1 / R-019.4): preprocess-strategy
    # axis on warm-init failure path mirrors the feature 017/018 axes above.
    from ledgerlinc_ocr.preprocessing.preprocess_strategy_optin import (
        derive_run_summary_preprocess_strategy_id as _derive_preprocess_strategy_id_019,
    )
    _failure_preprocess_strategy_id = _derive_preprocess_strategy_id_019(
        threaded_preprocess_strategy=preprocess_strategy_threaded,
        preprocess_lane=_warm_lane,
    )
    if _pp_profile is not None and _pp_profile.kind == "stub":
        from ledgerlinc_ocr.preprocessing.identifiers import (
            STUB_DEFAULT_DET_REC_VARIANT,
            STUB_DEFAULT_MODULE_SET,
            STUB_DEFAULT_PREPROCESS_STRATEGY,
            STUB_DEFAULT_RASTER_PROFILE,
            STUB_DEFAULT_REGION_STRATEGY,
        )

        _failure_module_set_id = STUB_DEFAULT_MODULE_SET
        _failure_det_rec_variant_id = STUB_DEFAULT_DET_REC_VARIANT
        _failure_raster_profile_id = STUB_DEFAULT_RASTER_PROFILE
        _failure_region_strategy_id = STUB_DEFAULT_REGION_STRATEGY
        _failure_preprocess_strategy_id = STUB_DEFAULT_PREPROCESS_STRATEGY
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
        module_set_id=_failure_module_set_id,
        det_rec_variant_id=_failure_det_rec_variant_id,
        # Feature 018 (T010 / T020 / R-018.1 / R-018.4 / R-018.8):
        # all three additive top-level fields wired. raster_profile_id
        # and region_strategy_id derived via derive_*. On the warm-init
        # failure path the orchestrator never ran, so
        # region_strategy_fallback_count is always 0.
        raster_profile_id=_failure_raster_profile_id,
        region_strategy_id=_failure_region_strategy_id,
        region_strategy_fallback_count=0,
        # Feature 019 (T006a / R-019.14): preprocess-strategy axis on
        # warm-init failure path. The orchestrator never ran, so
        # ocr_only_fallback_count is always 0.
        preprocess_strategy_id=_failure_preprocess_strategy_id,
        ocr_only_fallback_count=0,
        # Feature 020 (T028 / R-020.10 / MI-16 / MI-17): always-emit
        # the four evidence-gate fields on the warm-init failure path
        # too. No documents reached the gate, so state_counts is all-
        # zero, documents is empty, and the suppression counter is 0.
        # `evidence_gate_id` is still "v1" — the closed-vocabulary
        # identifier is profile-independent (data-model.md §9).
        evidence_gate_id="v1",
        evidence_gate_suppressed_fallback_count=0,
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
    registry: WarmProfileRegistry,
    plan: ResolvedRunPlan,
    *,
    module_set: object | None = None,
    det_rec_variant: object | None = None,
    preprocess_strategy_threaded: str | None = None,
) -> None:
    """Register a warm-instance factory for the live preprocessing profile.

    Fires only when ALL of these hold (Copilot review item 1):
      (a) preprocess is inside the executed slice;
      (b) the selected preprocess profile is live (not stub);
      (c) the live adapter for the (impl, lane) triple is **actually a
          real live adapter**, not a test-only stub-fallback wrapper.
          This is checked via ``stages.is_live_capable``.

    The factory's ``initialize()`` constructs ONE of two singleton engines
    depending on ``preprocess_strategy_threaded`` (Feature 019 / Q3 /
    R-019.16 / I-019.16):

    - When ``preprocess_strategy_threaded == "ocr-only-v1"``, it
      constructs the OCR-only PaddleOCR engine via
      ``ocr_only._get_ocr_engine(device, text_detection_model_name=…,
      text_recognition_model_name=…)``; PPStructureV3 stays unconstructed.
      Subsequent fallback documents (per FR-005 trigger) build
      PPStructureV3 on demand mid-run per R-019.10.
    - Otherwise (including ``None`` / ``"ppstructurev3"`` / identity
      defaults), it adopts PPStructureV3 via
      ``ocr._adopt_engine(_get_engine(device, …))`` — the historical
      feature 014–018 path; OCR-only's ``_OCR_ENGINE`` stays None.

    Each engine satisfies single-construction-per-process independently
    (feature 015 FR-001 + I-019.2). Subsequent per-document calls reuse
    whichever singleton was warmed.
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

    profile_is_gpu = profile.lane == "gpu"
    device_str = "gpu:0" if profile_is_gpu else "cpu"
    _is_ocr_only_strategy = False
    if preprocess_strategy_threaded is not None:
        from ledgerlinc_ocr.preprocessing.preprocess_strategies import (
            resolve_preprocess_strategy as _resolve_preprocess_strategy_019,
        )
        _is_ocr_only_strategy = (
            _resolve_preprocess_strategy_019(preprocess_strategy_threaded).kind
            == "ocr-only"
        )

    class _WarmPreprocessInstance:
        def initialize(self) -> None:
            if _is_ocr_only_strategy:
                from ledgerlinc_ocr.preprocessing import ocr_only as _ocr_only_mod

                # Pre-PR QA review: `DetRecVariant` exposes
                # `det_model_name` / `rec_model_name` (presets.py:352–353);
                # the PaddleOCR-side kwarg names
                # (`text_detection_model_name` / `text_recognition_model_name`)
                # are NOT attributes on `DetRecVariant`. Using the actual
                # attribute names so the variant selection is honored.
                _text_det_name: str | None = None
                _text_rec_name: str | None = None
                if det_rec_variant is not None:
                    _text_det_name = det_rec_variant.det_model_name
                    _text_rec_name = det_rec_variant.rec_model_name
                _ocr_only_mod._get_ocr_engine(
                    device=device_str,
                    text_detection_model_name=_text_det_name,
                    text_recognition_model_name=_text_rec_name,
                )
                return

            from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

            global _PREFLIGHT_READOUT
            if profile_is_gpu:
                # Feature 014 (T021 / T023 / FR-009): inline GPU gate.
                # Raises GpuPrerequisiteError on any non-success FR-001
                # state; caller (_warm_initialize_live_preprocess) catches
                # the exception and turns it into a run-level abort.
                from ledgerlinc_ocr.preprocessing.preflight import (
                    ensure_gpu_ready as _ensure_gpu_ready,
                )

                # Feature 017 (review CRITICAL fix): thread the resolved
                # presets into ensure_gpu_ready so the GPU engine
                # constructor receives the use_kwargs splat (R-017.6) and
                # det/rec model-name overrides (R-017.4 Appendix A).
                _PREFLIGHT_READOUT = _ensure_gpu_ready(
                    module_set=module_set,
                    det_rec_variant=det_rec_variant,
                )
            _ocr_mod._get_engine(device=device_str)  # type: ignore[attr-defined]

        def close(self) -> None:
            return None

    registry.register_factory(
        stage="preprocess",
        implementation="ppstructurev3",
        lane=profile.lane,
        factory=_WarmPreprocessInstance,
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
                GpuPrerequisiteError as _gpu_prerequisite_error_type,
            )
        except ImportError:
            _gpu_prerequisite_error_type = None  # type: ignore[assignment]
        if (
            _gpu_prerequisite_error_type is not None
            and isinstance(exc, _gpu_prerequisite_error_type)
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
