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
from typing import Any

from ledgerlinc_ocr.preprocessing import pipeline
from ledgerlinc_ocr.preprocessing.errors import (
    EXIT_INPUT_REJECTED,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_UNEXPECTED,
    EXIT_WARMUP_FAILED,
    ArtifactInvalidError,
    EngineInitError,
    InputRejectedError,
    WarmupError,
)
from ledgerlinc_ocr.preprocessing.warmup_optin import (
    is_warmup_optin_set,
    is_gpu_lane,
    warn_and_proceed_message,
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
    measure_total,
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
    # Feature 016 (T008 / FR-002 / R-016.1 / contracts/cli-contract.md §1):
    # opt-in GPU warmup pass for ppstructurev3@gpu. Off by default; orthogonal
    # to --preprocess-profile. Also accepted via the LEDGERLINC_GPU_WARMUP=1
    # env var (CLI flag wins when both set).
    p.add_argument(
        "--gpu-warmup",
        action="store_true",
        default=False,
        help=(
            "Run a one-time PPStructureV3 warmup pass after engine "
            "construction so MIOpen/COMGR kernel-selection cost is paid up "
            "front. Reported as phase_timings.warmup on the first successful "
            "per-document run_summary entry. Has no effect on "
            "ppstructurev3@cpu or stub adapters (a stderr warning is emitted "
            "in those cases). Can also be set via the LEDGERLINC_GPU_WARMUP=1 "
            "environment variable; the CLI flag wins when both are present."
        ),
    )
    # Feature 017 (T009 / R-017.1 / contracts/cli-contract.md §1): two
    # closed-vocabulary preset axes for the ppstructurev3@gpu lane. Both
    # default to None — the CPU/legacy default kicks in. Resolution happens
    # at argv parse time; UnknownPresetError fails fast with exit code 16
    # BEFORE any Paddle import. Orthogonal to --preprocess-profile and
    # --gpu-warmup. Also accepted via the LEDGERLINC_MODULE_SET and
    # LEDGERLINC_DET_REC_VARIANT environment variables (CLI flag wins
    # when both are set).
    p.add_argument(
        "--module-set",
        type=str,
        default=None,
        help=(
            "Select a named PPStructureV3 module-set preset for the "
            "ppstructurev3@gpu lane. Valid values: legacy, reduced-v1, "
            "cpu-default, stub-default. Default on GPU: legacy. The "
            "cpu-default / stub-default identity values are accepted on "
            "non-GPU profiles; any GPU value passed on a non-GPU profile "
            "is ignored with a stderr warning. Can also be set via the "
            "LEDGERLINC_MODULE_SET environment variable; the CLI flag "
            "wins when both are present."
        ),
    )
    p.add_argument(
        "--det-rec-variant",
        type=str,
        default=None,
        help=(
            "Select a named detection/recognition model variant for the "
            "ppstructurev3@gpu lane. Valid values: legacy, ppocrv5-mobile, "
            "ppocrv4-mobile, cpu-default, stub-default. Default on GPU: "
            "legacy. The cpu-default / stub-default identity values are "
            "accepted on non-GPU profiles; any GPU value passed on a "
            "non-GPU profile is ignored with a stderr warning. Can also "
            "be set via the LEDGERLINC_DET_REC_VARIANT environment "
            "variable; the CLI flag wins when both are present."
        ),
    )
    # Feature 018 (T009 / R-018.1 / contracts/cli-contract.md §1): one new
    # closed-vocabulary preset axis for the ppstructurev3@gpu lane (DPI).
    # Defaults to None — the CPU/legacy default kicks in. Resolution
    # happens at argv parse time; UnknownPresetError fails fast with exit
    # code 16 BEFORE any Paddle import (R-018.12). Orthogonal to
    # --preprocess-profile, --gpu-warmup, --module-set, --det-rec-variant.
    # Also accepted via the LEDGERLINC_RASTER_PROFILE env var (CLI flag
    # wins when both set).
    p.add_argument(
        "--raster-profile",
        type=str,
        default=None,
        help=(
            "Select a named rasterization-DPI preset for the "
            "ppstructurev3@gpu lane. Valid values: legacy, reduced-v1, "
            "cpu-default, stub-default. Default on GPU: legacy. The "
            "cpu-default / stub-default identity values are accepted on "
            "non-GPU profiles; any GPU value passed on a non-GPU profile "
            "is ignored with a stderr warning. Can also be set via the "
            "LEDGERLINC_RASTER_PROFILE environment variable; the CLI "
            "flag wins when both are present."
        ),
    )
    # Feature 018 (T019 / R-018.4 / contracts/cli-contract.md §1):
    # region-strategy axis (page-area targeting). Mirrors --raster-profile
    # above. Same parse-order, same UnknownPresetError → exit 16.
    p.add_argument(
        "--region-strategy",
        type=str,
        default=None,
        help=(
            "Select a named region-targeting strategy for the "
            "ppstructurev3@gpu lane. Valid values: full-page, "
            "header-first-v1, cpu-default, stub-default. Default on GPU: "
            "full-page. The header-first-v1 strategy processes only "
            "page 1's top-30%% header band; pages 2..N appear in "
            "preprocess_output.json.pages[] as empty records. On a "
            "no-evidence trigger (whitespace-stripped concat of "
            "blocks[].text in the targeted region empty), the strategy "
            "falls back to full-page on that document and increments "
            "region_strategy_fallback_count on run_summary. Can also "
            "be set via LEDGERLINC_REGION_STRATEGY; the CLI flag wins."
        ),
    )
    # Feature 019 (T009 / R-019.1 / R-019.2 / contracts/cli-contract.md §1):
    # preprocess-strategy axis (which preprocessing pipeline to invoke).
    # Mirrors --raster-profile / --region-strategy. Same parse-order, same
    # UnknownPresetError → exit 16.
    # Build the help text from named constants so the documented
    # thresholds track the registry definitions automatically (pre-PR
    # QA review: no hardcoded magic numbers in user-facing strings).
    from ledgerlinc_ocr.preprocessing.preprocess_strategies import (
        OCR_ONLY_MIN_CONFIDENCE_MEAN as _OCR_ONLY_MIN_CONFIDENCE_MEAN,
        OCR_ONLY_MIN_TOKEN_COUNT as _OCR_ONLY_MIN_TOKEN_COUNT,
    )
    p.add_argument(
        "--preprocess-strategy",
        type=str,
        default=None,
        help=(
            "Select a named preprocessing-strategy preset for the "
            "ppstructurev3@gpu lane. User-selectable values: "
            "ppstructurev3 (the default — layout-aware PPStructureV3) "
            "and ocr-only-v1 (PaddleOCR text-detection + text-recognition "
            "only — no layout / table / formula / seal modules). On the "
            "FR-005 combined two-threshold trigger (token count < "
            f"{_OCR_ONLY_MIN_TOKEN_COUNT} OR mean detector confidence "
            f"< {_OCR_ONLY_MIN_CONFIDENCE_MEAN:.2f}), the ocr-only-v1 "
            "strategy falls back to ppstructurev3 on that document and "
            "increments ocr_only_fallback_count on run_summary. "
            "(cpu-default and stub-default are internal identity values "
            "emitted on non-GPU profiles — not user-selectable.) "
            "Can also be set via LEDGERLINC_PREPROCESS_STRATEGY; the "
            "CLI flag wins."
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


def _handle_gpu_prerequisite_error(
    *,
    exc: Any,
    invocation: pipeline.Invocation,
    preprocess_lane: str,
    stage_timing: StageTiming,
    exit_code_for_state: Any,
) -> int:
    """Common handler for GpuPrerequisiteError raised either during the
    hoisted warmup pass or during `pipeline.run()` itself.

    Emits the FR-009 stderr envelope, then a partial single-doc
    `run_summary` carrying whatever phases the preflight probe captured
    before failing (paddle_import is the most common; gpu_bind_probe /
    engine_init only when the failure happened later in the classify
    ladder).
    """
    print(
        f"error: --preprocess-profile=ppstructurev3@gpu: "
        f"{exc.state.value}; {exc.recommendation}",
        file=sys.stderr,
    )
    _emit_single_doc_run_summary(
        invocation=invocation,
        preprocess_lane=preprocess_lane,
        stage_timing=stage_timing,
        success=False,
        failed_stage="preprocess",
        exit_code=exit_code_for_state(exc.state),
        message=f"--preprocess-profile=ppstructurev3@gpu: {exc.state.value}; {exc.recommendation}",
    )
    return exit_code_for_state(exc.state)


def _emit_engine_init_failed(exc: EngineInitError) -> None:
    """Emit the FR-016 `kind: "engine_init_failed"` stderr JSON envelope
    with optional weight-download diagnostic fields."""
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


def _emit_simple_error_kind(kind: str, message: str) -> None:
    """Emit the simple `{status:error, kind:<kind>, message:<msg>}` envelope
    used by input_rejected / artifact_invalid / unexpected branches."""
    print(
        json.dumps({"status": "error", "kind": kind, "message": message}),
        file=sys.stderr,
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
        _emit_simple_error_kind("input_rejected", str(exc))
        return EXIT_INPUT_REJECTED

    # Feature 017 (T009 / T020 / R-017.1 / R-017.9 / R-017.12 /
    # contracts/cli-contract.md §3 / Plan §I-7 step 1 + 2 / I-11): resolve
    # the two preset axes BEFORE Paddle import. UnknownPresetError fails
    # fast with exit code 16 (R-017.12). When a known value is set on a
    # non-GPU profile, emit FR-013 warn-and-proceed and drop the resolved
    # value (the CPU/stub identity-preset default flows into run_summary).
    from ledgerlinc_ocr.preprocessing.preset_optin import (
        resolve_module_set_value as _resolve_module_set_value,
        resolve_det_rec_variant_value as _resolve_det_rec_variant_value,
        is_gpu_lane as _is_gpu_lane_017,
        module_set_warn_message as _module_set_warn,
        det_rec_variant_warn_message as _det_rec_warn,
    )
    from ledgerlinc_ocr.preprocessing.presets import (
        resolve_module_set as _resolve_module_set,
        resolve_det_rec_variant as _resolve_det_rec_variant,
    )
    from ledgerlinc_ocr.preprocessing.errors import UnknownPresetError as _UnknownPresetError
    # Feature 018 (T009 / R-018.1 / R-018.12 / contracts/cli-contract.md §3 / §5):
    # raster_profile axis resolution mirrors feature 017's module_set
    # axis. Same parse order: env-var → resolve → cross-profile warn.
    from ledgerlinc_ocr.preprocessing.raster_profile_optin import (
        resolve_raster_profile_value as _resolve_raster_profile_value,
        raster_profile_warn_message as _raster_profile_warn,
    )
    from ledgerlinc_ocr.preprocessing.raster_profiles import (
        resolve_raster_profile as _resolve_raster_profile,
    )
    # Feature 018 (T019): region_strategy axis resolution.
    from ledgerlinc_ocr.preprocessing.region_strategy_optin import (
        resolve_region_strategy_value as _resolve_region_strategy_value,
        region_strategy_warn_message as _region_strategy_warn,
    )
    from ledgerlinc_ocr.preprocessing.region_strategies import (
        resolve_region_strategy as _resolve_region_strategy,
    )
    # Feature 019 (T009 / R-019.1 / R-019.12 / contracts/cli-contract.md §3 / §4):
    # preprocess_strategy axis resolution mirrors feature 017/018 axes.
    # Same parse order: env-var → resolve → cross-profile warn.
    from ledgerlinc_ocr.preprocessing.preprocess_strategy_optin import (
        resolve_preprocess_strategy_value as _resolve_preprocess_strategy_value,
        preprocess_strategy_warn_message as _preprocess_strategy_warn,
    )
    from ledgerlinc_ocr.preprocessing.preprocess_strategies import (
        resolve_user_preprocess_strategy as _resolve_user_preprocess_strategy,
    )

    _module_set_raw = _resolve_module_set_value(args.module_set)
    _det_rec_raw = _resolve_det_rec_variant_value(args.det_rec_variant)
    _raster_profile_raw = _resolve_raster_profile_value(args.raster_profile)
    _region_strategy_raw = _resolve_region_strategy_value(args.region_strategy)
    _preprocess_strategy_raw = _resolve_preprocess_strategy_value(
        args.preprocess_strategy
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
        print(
            f"error: unknown {exc.preset_axis}: {exc.preset_value!r} — "
            f"valid values are: {valid_str}",
            file=sys.stderr,
        )
        return int(exc.exit_code)
    # Cross-profile fail-safe (FR-013 / FR-014 / Plan §I-7 step 2 / I-11):
    # on a non-GPU profile, set values are warn-and-proceeded and dropped
    # (covers BOTH feature 017's two axes and feature 018's two axes).
    _module_set_threaded: str | None = _module_set_raw
    _det_rec_threaded: str | None = _det_rec_raw
    _raster_profile_threaded: str | None = _raster_profile_raw
    _region_strategy_threaded: str | None = _region_strategy_raw
    _preprocess_strategy_threaded: str | None = _preprocess_strategy_raw
    if not _is_gpu_lane_017(preprocess_lane):
        active_profile_name_017 = (
            args.preprocess_profile if args.preprocess_profile else "ppstructurev3@cpu"
        )
        if _module_set_raw is not None:
            print(_module_set_warn(active_profile_name_017), file=sys.stderr)
            _module_set_threaded = None
        if _det_rec_raw is not None:
            print(_det_rec_warn(active_profile_name_017), file=sys.stderr)
            _det_rec_threaded = None
        if _raster_profile_raw is not None:
            print(_raster_profile_warn(active_profile_name_017), file=sys.stderr)
            _raster_profile_threaded = None
        if _region_strategy_raw is not None:
            print(_region_strategy_warn(active_profile_name_017), file=sys.stderr)
            _region_strategy_threaded = None
        # Feature 019 (T028 / FR-013 / I-019.14): warn-and-proceed for the
        # preprocess_strategy axis on CPU/stub profiles. Same shape as
        # features 017/018 above.
        if _preprocess_strategy_raw is not None:
            print(_preprocess_strategy_warn(active_profile_name_017), file=sys.stderr)
            _preprocess_strategy_threaded = None

    # Feature 016 (T008 / T010 / T021 / FR-010 / SC-007): resolve the warmup
    # opt-in surface (CLI flag + LEDGERLINC_GPU_WARMUP env var). When set on
    # a non-GPU lane, emit the FR-010 warn-and-proceed line and force the
    # threaded `warmup` flag to False so `_run_inner` does not import or
    # invoke `preprocessing.warmup` (FR-011 / I-6).
    warmup_optin = is_warmup_optin_set(args.gpu_warmup)
    warmup_threaded = warmup_optin and is_gpu_lane(preprocess_lane)
    if warmup_optin and not is_gpu_lane(preprocess_lane):
        active_profile_name = (
            args.preprocess_profile if args.preprocess_profile else "ppstructurev3@cpu"
        )
        print(warn_and_proceed_message(active_profile_name), file=sys.stderr)

    invocation = pipeline.Invocation(
        document_folder=args.document_folder,
        source_file=args.source_file,
        write_page_images=args.write_page_images,
        pipeline_version=args.pipeline_version,
        preprocess_lane=preprocess_lane,
        warmup=warmup_threaded,
        module_set_id=_module_set_threaded,
        det_rec_variant_id=_det_rec_threaded,
        # Feature 018 (T009/T010): threaded raster_profile_id flows from
        # the resolved CLI flag / env var. None on non-GPU profiles
        # (warn-and-proceed already nulled it). The pipeline orchestrator
        # (T010) reads this and passes the resolved DPI to rasterize_pdf.
        raster_profile_id=_raster_profile_threaded,
        # Feature 018 (T019/T018): threaded region_strategy_id; same
        # discipline as raster_profile_id. The pipeline orchestrator
        # (T018) reads this and branches on the strategy class.
        region_strategy_id=_region_strategy_threaded,
        # Feature 019 (T009/T011): threaded preprocess_strategy_id; same
        # discipline as raster_profile_id / region_strategy_id. The
        # pipeline orchestrator (T011) reads this and dispatches on
        # PreprocessStrategy.kind (ppstructurev3 / ocr-only / identity).
        preprocess_strategy_id=_preprocess_strategy_threaded,
    )

    # Feature 016 (Copilot PR #24 round 2 finding 1 / FR-007 / SC-004):
    # warmup MUST run BEFORE the `measure_total(stage_timing)` window so
    # the captured warmup duration does not inflate
    # `phase_timings.total.seconds`. `run_warmup_if_active` is a no-op on
    # CPU/stub lanes — the warn-and-proceed line was already emitted
    # above. WarmupError translates to exit 15 + the canonical literal
    # stderr line per cli-contract.md §3-§4.
    try:
        pipeline.run_warmup_if_active(
            preprocess_lane=preprocess_lane,
            warmup_optin=warmup_optin,
            module_set_id=_module_set_threaded,
            det_rec_variant_id=_det_rec_threaded,
            # Feature 019 (T035 / R-019.16 / I-019.16): warmup binds the
            # engine implied by the selected preprocess_strategy_id.
            preprocess_strategy_id=_preprocess_strategy_threaded,
        )
    except WarmupError as exc:
        print(
            f"error: warmup failed: {exc.cause_class}: {exc}",
            file=sys.stderr,
        )
        return EXIT_WARMUP_FAILED
    except _GpuPrerequisiteError as exc:
        # GPU prereq probing during warmup's `ensure_gpu_ready()` call
        # raises here. Pre-measure_total path: stage_timing is empty
        # because no per-doc timing has started yet.
        return _handle_gpu_prerequisite_error(
            exc=exc,
            invocation=invocation,
            preprocess_lane=preprocess_lane,
            stage_timing=StageTiming(stage="preprocess"),
            exit_code_for_state=_exit_code_for_state,
        )

    # Feature 015 (T017): construct a StageTiming so pipeline.run() can
    # record the rasterization / artifact_write phase deltas. Per the
    # `pipeline.run()` contract (caller owns `measure_total` when
    # `stage_timing` is passed in), wrap the call in `measure_total`
    # here so the GPU-prereq failure path below also records elapsed
    # time even when pipeline.run() raises before completing.
    stage_timing = StageTiming(stage="preprocess")

    try:
        with measure_total(stage_timing):
            out_path = pipeline.run(invocation, stage_timing=stage_timing)
        with out_path.open("r", encoding="utf-8") as f:
            written = json.load(f)
    except _GpuPrerequisiteError as exc:
        # Post-measure_total path: stage_timing carries whatever phases
        # the GPU prereq probe completed before failing.
        return _handle_gpu_prerequisite_error(
            exc=exc,
            invocation=invocation,
            preprocess_lane=preprocess_lane,
            stage_timing=stage_timing,
            exit_code_for_state=_exit_code_for_state,
        )
    except InputRejectedError as exc:
        _emit_simple_error_kind("input_rejected", str(exc))
        return EXIT_INPUT_REJECTED
    except EngineInitError as exc:
        _emit_engine_init_failed(exc)
        return EXIT_INTERNAL_ERROR
    except ArtifactInvalidError as exc:
        _emit_simple_error_kind("artifact_invalid", str(exc))
        return EXIT_INTERNAL_ERROR
    except Exception as exc:
        _emit_simple_error_kind("unexpected", f"{type(exc).__name__}: {exc}")
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
    # Feature 016 (T006 / T008 / R-016.8): thread the cached warmup seconds
    # into the run_summary's first-doc one-time-GPU-phases attachment when
    # warmup actually ran.
    warmup_seconds: float | None = None
    if invocation.warmup and is_gpu_lane(preprocess_lane):
        from ledgerlinc_ocr.preprocessing import warmup as _warmup_mod
        warmup_seconds = _warmup_mod.get_cached_warmup_seconds()
    _emit_single_doc_run_summary(
        invocation=invocation,
        preprocess_lane=preprocess_lane,
        stage_timing=stage_timing,
        success=True,
        document_id=written["document_id"],
        warmup_seconds=warmup_seconds,
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
    *,
    warmup_seconds: float | None = None,
) -> None:
    """On a successful first GPU-lane document, attach the GPU one-time
    phase keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, and —
    feature 016 — `warmup`) from the cached preflight readout and the
    captured warmup seconds. CPU runs leave `phase_timings` untouched
    (FR-017 / ISO1).

    Feature 016 (T008 / R-016.8 / contracts/module-invariants.md I-11):
    the four "first-doc one-time GPU phase" keys form a coherent set —
    `attach_one_time_gpu_phases` is the single source of truth for the
    set's joint-presence rule.

    Delegates field-name mapping, six-decimal rounding, and None-omission
    rules to `pipeline.timing.attach_one_time_gpu_phases` so the warm-
    corpus and single-doc paths cannot drift.
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
    if readout is None and warmup_seconds is None:
        return
    timing_attach_one_time_gpu_phases(
        {"phase_timings": phase_timings},
        readout,
        warmup_seconds=warmup_seconds,
    )


def _drain_per_page_inference(
    preprocess_lane: str,
) -> list[tuple[int, float]] | None:
    """Drain the GPU per-page inference accumulator. Returns the recorded
    pages on the GPU lane; returns None on CPU/stub but still drains the
    accumulator so state cannot leak across calls (FR-017 / ISO1)."""
    from ledgerlinc_ocr.preprocessing import ocr as _ocr_mod

    drained = _ocr_mod.take_gpu_inference_per_page()
    if not preprocess_lane.startswith("gpu"):
        return None
    return drained


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
    warmup_seconds: float | None = None,
) -> None:
    """Emit the final `kind: "run_summary"` JSON line for a single-doc run.

    Single-doc emits the same shape as warm-corpus mode (R-015.6) so
    SC-005's "identify the slowest phase" analysis works the same way
    in both contexts. Output is the very last stdout line, after the
    existing `{"status": "ok", ...}` summary line.

    Feature 016 (T008 / R-016.8): the optional `warmup_seconds` keyword
    threads the captured warmup duration through to the run_summary's
    first-doc one-time-GPU-phases attachment. ``None`` means warmup did
    not run (CPU/stub or warmup opt-in absent); a float means warmup
    completed successfully."""
    phase_timings = _build_phase_timings_from_stage(stage_timing)

    # GPU one-time phases attach only on the GPU lane.
    _attach_one_time_gpu_phases(
        phase_timings, preprocess_lane, warmup_seconds=warmup_seconds
    )

    # GPU per-page inference array (drained from ocr accumulator).
    per_page_inference = _drain_per_page_inference(preprocess_lane)

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

    # Feature 017 (review CRITICAL fix): thread the resolved preset
    # identifiers from `Invocation` onto `RunSummary` so a GPU run with
    # `--module-set=reduced-v1` actually emits `module_set_id="reduced-v1"`
    # on the wire (FR-008 / FR-010 / SC-003). Previously the dataclass
    # defaults (`cpu-default`) reached the wire on every run; now the
    # CLI-resolved value flows through.
    from ledgerlinc_ocr.preprocessing.preset_optin import (
        derive_run_summary_identifiers as _derive_identifiers_017,
    )
    # Feature 018 (T009 / T010 / R-018.1 / FR-008 / FR-011 / SC-004):
    # same threading discipline for the raster_profile axis.
    from ledgerlinc_ocr.preprocessing.raster_profile_optin import (
        derive_run_summary_raster_profile_id as _derive_raster_profile_id_018,
    )
    # Feature 018 (T019 / T020 / R-018.4 / R-018.8): same threading
    # discipline for the region_strategy axis. The fallback count comes
    # from `invocation.region_strategy_fallback_fired` set by the
    # orchestrator's region-first path on FR-007 trigger.
    from ledgerlinc_ocr.preprocessing.region_strategy_optin import (
        derive_run_summary_region_strategy_id as _derive_region_strategy_id_018,
    )
    # Feature 019 (T006a / T009 / T011 / R-019.1 / R-019.10 / FR-007 / FR-008):
    # same threading discipline for the preprocess_strategy axis. The
    # ocr_only_fallback count comes from `invocation.ocr_only_fallback_fired`
    # set by the orchestrator's OCR-only path on FR-005 trigger (US3 / T021).
    from ledgerlinc_ocr.preprocessing.preprocess_strategy_optin import (
        derive_run_summary_preprocess_strategy_id as _derive_preprocess_strategy_id_019,
    )

    _module_set_id_017, _det_rec_variant_id_017 = _derive_identifiers_017(
        threaded_module_set=invocation.module_set_id,
        threaded_det_rec_variant=invocation.det_rec_variant_id,
        preprocess_lane=preprocess_lane,
    )
    _raster_profile_id_018 = _derive_raster_profile_id_018(
        threaded_raster_profile=invocation.raster_profile_id,
        preprocess_lane=preprocess_lane,
    )
    _region_strategy_id_018 = _derive_region_strategy_id_018(
        threaded_region_strategy=invocation.region_strategy_id,
        preprocess_lane=preprocess_lane,
    )
    _preprocess_strategy_id_019 = _derive_preprocess_strategy_id_019(
        threaded_preprocess_strategy=invocation.preprocess_strategy_id,
        preprocess_lane=preprocess_lane,
    )
    # R-018.8 / Clarifications Q4: per-doc fallback flag from the
    # orchestrator → per-run accumulator (single-doc CLI = 0 or 1).
    _region_strategy_fallback_count_018 = (
        1 if invocation.region_strategy_fallback_fired else 0
    )
    # R-019.10 / I-019.4: same per-doc → per-run mapping for the OCR-only
    # fallback flag (single-doc CLI = 0 or 1).
    _ocr_only_fallback_count_019 = (
        1 if getattr(invocation, "ocr_only_fallback_fired", False) else 0
    )
    # Feature 020 (T029 / R-020.7 / R-020.10 / R-020.11 / FR-003 /
    # FR-006): evaluate the evidence gate on the FINAL preprocess_output.json
    # for the single-document path. Mirrors the corpus_run.py per-success
    # wiring (T028). On failure-path (`documents_succeeded == 0`) the
    # gate skips and accumulators stay at defaults — the always-emit
    # contract per MI-16 / MI-17 still ships the four `run_summary`
    # fields with default-zero values.
    _evidence_gate_state_counts_020: dict[str, int] = {
        "sufficient": 0,
        "borderline": 0,
        "insufficient": 0,
    }
    _evidence_gate_documents_020: list[dict[str, Any]] = []
    if documents_succeeded == 1:
        try:
            from ledgerlinc_ocr.preprocessing.evidence_gate import (
                build_evidence_gate_document_record,
                evaluate_evidence_gate,
                load_preprocess_output_for_gate,
            )

            _gate_input = load_preprocess_output_for_gate(
                invocation.document_folder / "preprocess_output.json"
            )
            if _gate_input is not None:
                _gate_result = evaluate_evidence_gate(_gate_input)
                _evidence_gate_state_counts_020[_gate_result.decision] += 1
                _evidence_gate_documents_020.append(
                    build_evidence_gate_document_record(
                        document_id=document_id or invocation.document_folder.name,
                        result=_gate_result,
                    )
                )
        except Exception:  # noqa: BLE001 — gate failure must not break the run
            # Defensive — bug in the gate module surfaces as a missing
            # per-doc record, not an aborted CLI invocation.
            pass
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
        module_set_id=_module_set_id_017,
        det_rec_variant_id=_det_rec_variant_id_017,
        # ppstructure_modules_invoked left at default `[]` until T010's
        # GPU audit-callable invocation lands (deferred per FR-024).
        # Feature 018 (T009 / T019 / T020): all three additive top-level
        # fields wired. raster_profile_id from US1's CLI; region_strategy_id
        # from US2's CLI; region_strategy_fallback_count from the
        # orchestrator's per-doc fallback flag (R-018.8 / Q4 — single-doc
        # CLI takes the value zero or one).
        raster_profile_id=_raster_profile_id_018,
        region_strategy_id=_region_strategy_id_018,
        region_strategy_fallback_count=_region_strategy_fallback_count_018,
        # Feature 019 (T006a / T011 / T022): two additive top-level fields.
        # preprocess_strategy_id derived via derive_*; ocr_only_fallback_count
        # from the orchestrator's per-doc fallback flag (R-019.10 / I-019.4 —
        # single-doc CLI = 0 or 1).
        preprocess_strategy_id=_preprocess_strategy_id_019,
        ocr_only_fallback_count=_ocr_only_fallback_count_019,
        # Feature 020 (T029 / R-020.10 / MI-16 / MI-17): four additive
        # top-level fields. Same wiring discipline as corpus_run.py —
        # `evidence_gate_id` is `"v1"` uniformly; `state_counts` and
        # `documents` come from the single-doc accumulator above (or
        # the all-zero defaults if the doc failed); suppression counter
        # stays at 0 on the MVP slice.
        evidence_gate_id="v1",
        evidence_gate_state_counts=_evidence_gate_state_counts_020,
        evidence_gate_documents=_evidence_gate_documents_020,
        evidence_gate_suppressed_fallback_count=0,
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
