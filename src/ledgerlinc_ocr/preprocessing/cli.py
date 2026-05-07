"""argparse CLI for the preprocessing slice (research Decision 9).

Feature 014 (T022): adds `--preprocess-profile` argument that accepts
the closed-set vocabulary from `pipeline.profiles` (default
``ppstructurev3@cpu``; ``ppstructurev3@gpu`` is the new opt-in lane).
Catches `GpuPrerequisiteError` raised by the inline gate in T021 and
exits with the FR-001-state-mapped exit code per Contracts §1.

Feature 015 (T017 / R-015.6 / FR-014): single-doc runs now emit a
final `kind: "run_summary"` JSON line on stdout with `documents_total: 1`,
the structured `phase_timings` block per FR-014 + Q3, and the
`per_page_inference` array on the GPU lane. Previous status JSON line
is preserved before the run_summary line for back-compat with
existing consumers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ledgerlinc_ocr.preprocessing import pipeline
from ledgerlinc_ocr.preprocessing.errors import (
    EXIT_INPUT_REJECTED,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_UNEXPECTED,
    ArtifactInvalidError,
    EngineInitError,
    InputRejectedError,
)
from ledgerlinc_ocr.pipeline.profiles import (
    PPSTRUCTUREV3_CPU,
    ProfileValidationError,
    parse_profile,
)
from ledgerlinc_ocr.pipeline.timing import (
    DocumentTimings,
    RunSummary,
    StageTiming,
    attach_one_time_gpu_phases as timing_attach_one_time_gpu_phases,
    build_per_document_failure,
    build_per_document_success,
    emit_run_summary,
)

# Feature 014 / VT-003: `preflight` types (GpuPrerequisiteError,
# exit_code_for_state) are imported lazily inside `main()`'s
# exception handler. Module-level import would break collection
# for unrelated tests when `preflight.py` is temporarily unavailable
# (T035 collection-time defensive path). The CPU path never raises
# GpuPrerequisiteError, so the lazy import never fires on CPU runs.


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledgerlinc-preprocess",
        description="Stage 1 PDF preprocessing (rasterize + OCR + layout + quality).",
    )
    p.add_argument("--document-folder", type=Path, required=True)
    p.add_argument("--source-file", type=str, default="source.pdf")
    p.add_argument("--write-page-images", action="store_true")
    p.add_argument("--pipeline-version", type=str, default=None)
    # Feature 014 (T022): closed-vocabulary preprocess-profile flag.
    # Default is ppstructurev3@cpu (FR-008); ppstructurev3@gpu is the
    # opt-in workstation lane gated by the FR-001 preflight (T021).
    p.add_argument(
        "--preprocess-profile",
        type=str,
        default=None,
        help=(
            "Preprocessing profile. Default: ppstructurev3@cpu. "
            "Workstation GPU lane: ppstructurev3@gpu (gated by preflight; "
            "see docs/stage1-vendor-identity/paddle-gpu-preflight.md). "
            "Other values are rejected per the closed vocabulary in "
            "ledgerlinc_ocr.pipeline.profiles."
        ),
    )
    return p


def _resolve_preprocess_lane(raw_value: str | None) -> str:
    """Parse --preprocess-profile through the closed vocabulary and
    return the lane string ('cpu' or 'gpu0')."""
    raw = raw_value or PPSTRUCTUREV3_CPU
    profile = parse_profile("preprocess", raw)
    if profile.lane == "cpu":
        return "cpu"
    if profile.lane == "gpu":
        # Single-doc CLI uses device 0 by default; multi-GPU is reserved
        # for future work per Out Of Scope and R-014.8.
        return "gpu0"
    raise ProfileValidationError(
        f"--preprocess-profile={raw!r}: unsupported lane {profile.lane!r} for preprocessing"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Lazy import: only fires when main() is actually called. Module-level
    # `import preprocessing.cli` (e.g., during pytest collection) does NOT
    # trigger this import, so a missing preflight.py does NOT break
    # collection of unrelated tests (analyze finding VT-003 / T035).
    from ledgerlinc_ocr.preprocessing.preflight import (
        GpuPrerequisiteError as _GpuPrerequisiteError,
        exit_code_for_state as _exit_code_for_state,
    )

    try:
        preprocess_lane = _resolve_preprocess_lane(args.preprocess_profile)
    except ProfileValidationError as exc:
        print(
            json.dumps({"status": "error", "kind": "input_rejected", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INPUT_REJECTED

    invocation = pipeline.Invocation(
        document_folder=args.document_folder,
        source_file=args.source_file,
        write_page_images=args.write_page_images,
        pipeline_version=args.pipeline_version,
        preprocess_lane=preprocess_lane,
    )

    # Feature 015 (T017): construct a StageTiming so pipeline.run() can
    # record the rasterization / artifact_write phase deltas plus
    # measure_total. We thread it in as the new optional kwarg.
    stage_timing = StageTiming(stage="preprocess")

    try:
        out_path = pipeline.run(invocation, stage_timing=stage_timing)
        with out_path.open("r", encoding="utf-8") as f:
            written = json.load(f)
    except _GpuPrerequisiteError as exc:
        # Feature 014 (T022 / FR-009): name both the selected profile
        # and the FR-001 state in stderr; exit with the FR-001-state
        # exit code (10/11/12/13/14) per Contracts §1.
        print(
            f"error: --preprocess-profile=ppstructurev3@gpu: "
            f"{exc.state.value}; {exc.recommendation}",
            file=sys.stderr,
        )
        # Feature 015 (T018): emit a partial run_summary with whatever
        # phases the GPU prereq probe completed before failure (paddle
        # import is the most likely; gpu_bind_probe / engine_init only
        # if the failure happened later in the classify ladder).
        _emit_single_doc_run_summary(
            invocation=invocation,
            preprocess_lane=preprocess_lane,
            stage_timing=stage_timing,
            success=False,
            failed_stage="preprocess",
            exit_code=_exit_code_for_state(exc.state),
            message=f"--preprocess-profile=ppstructurev3@gpu: {exc.state.value}; {exc.recommendation}",
        )
        return _exit_code_for_state(exc.state)
    except InputRejectedError as exc:
        print(
            json.dumps({"status": "error", "kind": "input_rejected", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INPUT_REJECTED
    except EngineInitError as exc:
        payload: dict[str, object] = {
            "status": "error",
            "kind": "engine_init_failed",
            "cause_class": exc.cause_class,
            "cause_module": exc.cause_module,
            "message": str(exc),
        }
        if exc.missing_weight is not None:
            payload["missing_weight"] = exc.missing_weight
        if exc.weight_hoster_url is not None:
            payload["weight_hoster_url"] = exc.weight_hoster_url
        print(json.dumps(payload), file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    except ArtifactInvalidError as exc:
        print(
            json.dumps({"status": "error", "kind": "artifact_invalid", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INTERNAL_ERROR
    except Exception as exc:
        print(
            json.dumps({"status": "error", "kind": "unexpected", "message": f"{type(exc).__name__}: {exc}"}),
            file=sys.stderr,
        )
        return EXIT_UNEXPECTED

    print(
        json.dumps(
            {
                "status": "ok",
                "document_id": written["document_id"],
                "artifact": str(out_path),
                "warnings": len(written.get("warnings", [])),
            }
        )
    )

    # Feature 015 (T017 / R-015.6 / FR-014): emit the run_summary line
    # with the new structured phase_timings + per_page_inference blocks.
    _emit_single_doc_run_summary(
        invocation=invocation,
        preprocess_lane=preprocess_lane,
        stage_timing=stage_timing,
        success=True,
        document_id=written["document_id"],
    )

    return EXIT_OK


def _build_phase_timings_from_stage(
    stage_timing: StageTiming,
) -> dict[str, dict[str, float]]:
    """Convert `StageTiming.phases_ns` into the FR-014 structured form.

    Returns `{<phase_name>: {"seconds": <float>}}` for every recorded
    phase, plus `total: {"seconds": <float>}` derived from
    `stage_timing.total_ns`. Phases not recorded (e.g., `artifact_write`
    when the run aborted before write) are absent from the dict — never
    set to zero (FR-016)."""
    phase_timings: dict[str, dict[str, float]] = {}
    for phase_key, ns in stage_timing.phases_ns.items():
        phase_timings[phase_key] = {"seconds": round(ns / 1e9, 6)}
    if stage_timing.total_ns > 0:
        phase_timings["total"] = {"seconds": round(stage_timing.total_ns / 1e9, 6)}
    return phase_timings


def _attach_one_time_gpu_phases(
    phase_timings: dict[str, dict[str, float]],
    preprocess_lane: str,
) -> None:
    """On a successful first GPU-lane document, attach the GPU one-time
    phase keys (`paddle_import`, `gpu_bind_probe`, `engine_init`) from
    the cached preflight readout. CPU runs leave `phase_timings`
    untouched (FR-017 / ISO1).

    Delegates field-name mapping and None-omission rules to
    `pipeline.timing.attach_one_time_gpu_phases` so the warm-corpus
    and single-doc paths cannot drift.
    """
    if not preprocess_lane.startswith("gpu"):
        return
    try:
        from ledgerlinc_ocr.preprocessing.preflight import (
            get_last_readout as _get_last_readout,
        )
    except ImportError:
        return
    readout = _get_last_readout()
    if readout is None:
        return
    timing_attach_one_time_gpu_phases(
        {"phase_timings": phase_timings}, readout
    )


def _emit_single_doc_run_summary(
    *,
    invocation: pipeline.Invocation,
    preprocess_lane: str,
    stage_timing: StageTiming,
    success: bool,
    document_id: str | None = None,
    failed_stage: str | None = None,
    exit_code: int | None = None,
    message: str | None = None,
) -> None:
    """Emit the final `kind: "run_summary"` JSON line for a single-doc run.

    Single-doc emits the same shape as warm-corpus mode (R-015.6) so
    SC-005's "identify the slowest phase" analysis works the same way
    in both contexts. Output is the very last stdout line, after the
    existing `{"status": "ok", ...}` summary line."""
    phase_timings = _build_phase_timings_from_stage(stage_timing)

    # GPU one-time phases attach only on the GPU lane.
    _attach_one_time_gpu_phases(phase_timings, preprocess_lane)

    # GPU per-page inference array (drained from ocr accumulator).
    per_page_inference: list[tuple[int, float]] | None = None
    if preprocess_lane.startswith("gpu"):
        from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

        per_page_inference = _ocr_mod.take_gpu_inference_per_page()
    else:
        # CPU lane: drain to avoid leaking accumulator state across calls
        # but do NOT attach to the run_summary (FR-017 / ISO1).
        from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

        _ocr_mod.take_gpu_inference_per_page()

    folder_str = str(invocation.document_folder)
    doc_timings = DocumentTimings(stages={"preprocess": stage_timing})

    if success:
        per_doc_record = build_per_document_success(
            document_id=document_id or invocation.document_folder.name,
            folder=folder_str,
            timings=doc_timings,
            phase_timings=phase_timings,
            per_page_inference=per_page_inference,
        )
        documents_succeeded = 1
        documents_failed = 0
    else:
        per_doc_record = build_per_document_failure(
            document_id=document_id or invocation.document_folder.name,
            folder=folder_str,
            failed_stage=failed_stage or "preprocess",
            exit_code=exit_code if exit_code is not None else EXIT_INTERNAL_ERROR,
            message=message or "single-doc preprocess failure",
            timings=doc_timings if stage_timing.phases_ns or stage_timing.total_ns else None,
            phase_timings=phase_timings if phase_timings else None,
            per_page_inference=per_page_inference,
        )
        documents_succeeded = 0
        documents_failed = 1

    summary = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": _profile_slug_for_lane(preprocess_lane)},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=1,
        documents_succeeded=documents_succeeded,
        documents_failed=documents_failed,
        per_document=[per_doc_record],
        preprocess_lane=preprocess_lane,
    )
    emit_run_summary(summary)


def _profile_slug_for_lane(lane: str) -> str:
    """Reverse-map the lane string back to the canonical profile slug
    for `resolved_profiles`. CPU → ppstructurev3@cpu; gpu0 → ppstructurev3@gpu."""
    if lane == "cpu":
        return "ppstructurev3@cpu"
    if lane.startswith("gpu"):
        return "ppstructurev3@gpu"
    return lane


if __name__ == "__main__":
    raise SystemExit(main())
