"""GPU MVP demo orchestrator (T034).

Drives the lifecycle from data-model.md §8:

    argparse → voter-config → canonicalize document folder → source.pdf check
    → readiness checks 1–6 → eager-delete 4 canonical artifacts
    → preprocess → extract → route → assemble
    → readiness checks 7–8 (schema validation, runtime timeout report)
    → post-run CPU-fallback interrogation
    → assemble DemoRunReport
    → emit single JSON line to stdout; exit per ExitCode

This module exposes ``run(args)`` returning the appropriate ``ExitCode``.
``cli.main()`` wires argparse → this entry point (T035).

**Composition note (R-023.1).** The four pipeline phases are invoked
in-process via the ``PipelineComposer`` Protocol, which the default
implementation wires to features 003/005/008/009. Tests substitute a
stub composer to exercise the orchestration logic without booting the
real pipeline. The workstation manual GPU smoke run uses the default
composer.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol

from dartwing_ocr.gpu_demo import cpu_fallback as cpu_fallback_mod
from dartwing_ocr.gpu_demo import diagnostics
from dartwing_ocr.gpu_demo import evaluator_subprocess as evaluator_mod
from dartwing_ocr.gpu_demo import log
from dartwing_ocr.gpu_demo import quality_derivation as quality_mod
from dartwing_ocr.gpu_demo.enums import (
    BOUNDED_TIMEOUT_SECONDS,
    CANONICAL_ARTIFACT_BASENAMES,
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_CONTEXT_LENGTH,
    DEMO_REPORT_SCHEMA_VERSION,
    FailureKind,
    QualityStatus,
    QualityStatusSource,
    RuntimeOutcome,
    StalledPhase,
)
from dartwing_ocr.gpu_demo.exit_codes import ExitCode
from dartwing_ocr.gpu_demo.quality_status import EvaluatorVerdict
from dartwing_ocr.gpu_demo.folder_canonicalize import (
    EagerDeleteError,
    canonicalize_document_folder,
    safe_eager_delete,
)
from dartwing_ocr.gpu_demo.readiness.base import ReadinessContext
from dartwing_ocr.gpu_demo.readiness.runner import (
    first_failing_check_name,
    overall_passed,
    run_post_pipeline,
    run_pre_pipeline,
)
from dartwing_ocr.gpu_demo.report import (
    CPUFallbackDetection,
    DemoRunReport,
    PhaseTimings,
    ReadinessCheck,
    ReadinessSummary,
)
from dartwing_ocr.gpu_demo.run_id import new_run_id
from dartwing_ocr.gpu_demo.serialization import to_json_line
from dartwing_ocr.gpu_demo.version import get_pipeline_version
from dartwing_ocr.gpu_demo.voter_config_loader import (
    VoterConfigError,
    VoterConfigReference,
    load_voter_config,
)


class PipelineComposer(Protocol):
    """Pluggable composer for the four canonical pipeline phases (R-023.1)."""

    def preprocess(self, document_folder: Path, preset: str) -> Any: ...
    def extract(self, document_folder: Path, voter_config: VoterConfigReference) -> Any: ...
    def route(self, document_folder: Path) -> Any: ...
    def assemble(self, document_folder: Path) -> Any: ...


class _DefaultPipelineComposer:
    """Default composer wiring features 003/005/008/009 in-process.

    Each phase imports its sub-module lazily so the demo CLI can be
    imported without booting Paddle/extract/router/assembler. The actual
    function signatures wire to the per-feature ``pipeline.run`` entry
    points; deeper composition details belong to a follow-on session
    that inspects each sub-module's current public API. This default
    raises :class:`PipelineUnavailable` so the orchestrator surfaces a
    clear ``failed_at_<phase>`` runtime outcome on workstations where
    the sub-modules cannot import (e.g., CI without ROCm).
    """

    def preprocess(self, document_folder: Path, preset: str) -> Any:
        raise PipelineUnavailable(
            "preprocess",
            (
                "Default in-process pipeline composition (R-023.1) is pending "
                "the workstation-side smoke session that wires the real "
                "feature 003/014/018 entry points. Provide a custom "
                "PipelineComposer to run the demo against a stubbed pipeline."
            ),
        )

    def extract(self, document_folder: Path, voter_config: VoterConfigReference) -> Any:
        raise PipelineUnavailable("extract", "see preprocess")

    def route(self, document_folder: Path) -> Any:
        raise PipelineUnavailable("route", "see preprocess")

    def assemble(self, document_folder: Path) -> Any:
        raise PipelineUnavailable("assemble", "see preprocess")


class PipelineUnavailable(RuntimeError):
    """Raised when a pipeline composer cannot run the requested phase."""

    def __init__(self, phase: StalledPhase, message: str) -> None:
        super().__init__(f"{phase}: {message}")
        self.phase: StalledPhase = phase


@dataclass(frozen=True)
class OrchestratorOptions:
    """All inputs the orchestrator needs to drive a single run."""

    check_only: bool
    document_folder: Path
    voter_config_override: Optional[Path]
    preset: str
    with_evaluator: bool
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    ollama_context_length: int = DEFAULT_OLLAMA_CONTEXT_LENGTH
    bounded_timeout_seconds: int = BOUNDED_TIMEOUT_SECONDS
    composer: Optional[PipelineComposer] = None  # None = default in-process composer


def _build_options_from_args(args: argparse.Namespace) -> OrchestratorOptions:
    return OrchestratorOptions(
        check_only=bool(args.check_only),
        document_folder=Path(args.document_folder),
        voter_config_override=Path(args.voter_config) if args.voter_config else None,
        preset=str(args.preset),
        with_evaluator=bool(args.with_evaluator),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        ollama_context_length=int(
            os.environ.get("OLLAMA_CONTEXT_LENGTH", str(DEFAULT_OLLAMA_CONTEXT_LENGTH))
        ),
    )


def _build_check_results(results) -> list[ReadinessCheck]:
    """Coerce ReadinessResult objects into the report's ReadinessCheck shape."""
    out: list[ReadinessCheck] = []
    for r in results:
        out.append(
            ReadinessCheck(
                name=r.name,
                status=r.status,
                elapsed_seconds=r.elapsed_seconds,
                diagnostic=r.diagnostic,
            )
        )
    return out


def _assemble_readiness_summary(pre_results, post_results, elapsed_seconds: float) -> ReadinessSummary:
    all_results = list(pre_results) + list(post_results)
    return ReadinessSummary(
        checks=_build_check_results(all_results),
        overall_passed=overall_passed(all_results),
        elapsed_seconds=elapsed_seconds,
    )


def _empty_phase_timings() -> PhaseTimings:
    return PhaseTimings()


def _all_null_cpu_fallback() -> CPUFallbackDetection:
    return CPUFallbackDetection(
        ollama_post_run="skipped",
        paddle_post_run="skipped",
        pre_run_ollama_snapshot=None,
        post_run_ollama_snapshot=None,
    )


def _emit_report(report: DemoRunReport) -> None:
    """Write the single-line JSON DemoRunReport to stdout."""
    sys.stdout.write(to_json_line(report))
    sys.stdout.flush()


def _exit_code_for(
    runtime_outcome: Optional[RuntimeOutcome],
    failure_kind: Optional[FailureKind],
) -> ExitCode:
    """Map (runtime_outcome, failure_kind) → closed exit-code table (FR-021)."""
    if runtime_outcome == "success":
        return ExitCode.SUCCESS
    if failure_kind == "readiness-failed":
        return ExitCode.READINESS_FAILED
    if failure_kind == "invalid-input":
        return ExitCode.INVALID_INPUT
    if runtime_outcome == "timeout" or failure_kind == "pipeline-runtime-timeout":
        return ExitCode.PIPELINE_RUNTIME_TIMEOUT
    if failure_kind == "artifact-schema-validation-failed":
        return ExitCode.ARTIFACT_SCHEMA_VALIDATION_FAILED
    return ExitCode.PIPELINE_RUNTIME_ERROR


def _build_report(
    *,
    options: OrchestratorOptions,
    voter_ref: Optional[VoterConfigReference],
    readiness: ReadinessSummary,
    runtime_outcome: Optional[RuntimeOutcome],
    stalled_phase: Optional[StalledPhase],
    failure_kind: Optional[FailureKind],
    failing_check_name: Optional[str],
    phase_timings: PhaseTimings,
    total_runtime_seconds: Optional[float],
    artifact_paths: Optional[list[str]],
    quality_status: Optional[QualityStatus],
    quality_status_source: Optional[QualityStatusSource],
    cpu_fallback: CPUFallbackDetection,
    diagnostic: Optional[str],
    run_id: str,
) -> DemoRunReport:
    return DemoRunReport(
        schema_version=DEMO_REPORT_SCHEMA_VERSION,
        pipeline_version=get_pipeline_version(),
        run_id=run_id,
        interpreter_path=os.path.realpath(sys.executable),
        voter_config_path=voter_ref.path if voter_ref else None,
        expected_extraction_model=voter_ref.model_name if voter_ref else None,
        document_folder=str(options.document_folder.resolve())
        if not options.check_only and options.document_folder.exists()
        else None,
        bounded_timeout_seconds=options.bounded_timeout_seconds,
        readiness=readiness,
        runtime_outcome=runtime_outcome,
        stalled_phase=stalled_phase,
        failure_kind=failure_kind,
        failing_check_name=failing_check_name,  # type: ignore[arg-type]
        phase_timings=phase_timings,
        total_runtime_seconds=total_runtime_seconds,
        artifact_paths=artifact_paths,
        quality_status=quality_status,
        quality_status_source=quality_status_source,
        cpu_fallback_detection=cpu_fallback,
        diagnostic=diagnostic,
    )


def run(args: argparse.Namespace) -> int:
    """Top-level orchestrator entry. Returns the exit code (int).

    Lifecycle ordering matches ``data-model.md`` §8.
    """
    options = _build_options_from_args(args)
    run_id = new_run_id()

    # ------------------------------------------------------------------
    # 1. Voter-config load (exit 2 on any failure).
    # ------------------------------------------------------------------
    try:
        voter_ref = load_voter_config(options.voter_config_override)
    except VoterConfigError as exc:
        log.error(run_id, f"invalid input: {exc}")
        report = _build_report(
            options=options,
            voter_ref=None,
            readiness=ReadinessSummary(checks=[], overall_passed=False, elapsed_seconds=0.0),
            runtime_outcome=None,
            stalled_phase=None,
            failure_kind="invalid-input",
            failing_check_name=None,
            phase_timings=_empty_phase_timings(),
            total_runtime_seconds=None,
            artifact_paths=None,
            quality_status=None,
            quality_status_source=None,
            cpu_fallback=_all_null_cpu_fallback(),
            diagnostic=f"voter-config: {exc}",
            run_id=run_id,
        )
        _emit_report(report)
        return int(ExitCode.INVALID_INPUT)

    if voter_ref.extra_voters_ignored:
        log.warn(
            run_id,
            "voter config has multiple voters; demo uses the first "
            f"(model: {voter_ref.model_name})",
        )

    # ------------------------------------------------------------------
    # 2. Canonicalize document folder (skipped under --check-only).
    # ------------------------------------------------------------------
    canonical_folder: Optional[Path] = None
    if not options.check_only:
        try:
            canonical_folder = canonicalize_document_folder(options.document_folder)
        except EagerDeleteError as exc:
            log.error(run_id, f"invalid input: {exc}")
            report = _build_report(
                options=options,
                voter_ref=voter_ref,
                readiness=ReadinessSummary(checks=[], overall_passed=False, elapsed_seconds=0.0),
                runtime_outcome=None,
                stalled_phase=None,
                failure_kind="invalid-input",
                failing_check_name=None,
                phase_timings=_empty_phase_timings(),
                total_runtime_seconds=None,
                artifact_paths=None,
                quality_status=None,
                quality_status_source=None,
                cpu_fallback=_all_null_cpu_fallback(),
                diagnostic=f"document-folder: {exc}",
                run_id=run_id,
            )
            _emit_report(report)
            return int(ExitCode.INVALID_INPUT)

        # 3a. source.pdf existence gate (FR-027).
        source_pdf = canonical_folder / "source.pdf"
        if not source_pdf.exists():
            log.error(
                run_id,
                f"invalid input: source.pdf not found in {canonical_folder}",
            )
            report = _build_report(
                options=options,
                voter_ref=voter_ref,
                readiness=ReadinessSummary(checks=[], overall_passed=False, elapsed_seconds=0.0),
                runtime_outcome=None,
                stalled_phase=None,
                failure_kind="invalid-input",
                failing_check_name=None,
                phase_timings=_empty_phase_timings(),
                total_runtime_seconds=None,
                artifact_paths=None,
                quality_status=None,
                quality_status_source=None,
                cpu_fallback=_all_null_cpu_fallback(),
                diagnostic=f"source.pdf not found in {canonical_folder}",
                run_id=run_id,
            )
            _emit_report(report)
            return int(ExitCode.INVALID_INPUT)

    # Inform operator about ignored flags under --check-only (Q1/Q2/Q11).
    if options.check_only:
        if any([
            str(options.document_folder) != "tests/stage1_vendor_identity/inv_001_easy",
            options.preset != "header-first-v1",
            options.with_evaluator,
        ]):
            log.info(
                run_id,
                "ignoring --document-folder / --preset / --with-evaluator under --check-only",
            )

    # ------------------------------------------------------------------
    # 3. Readiness pre-pipeline checks (1–6).
    # ------------------------------------------------------------------
    pre_start = time.monotonic()
    base_context = ReadinessContext(
        run_id=run_id,
        interpreter_path=os.path.realpath(sys.executable),
        voter_config_path=voter_ref.path,
        expected_extraction_model=voter_ref.model_name,
        document_folder=canonical_folder,
        ollama_base_url=options.ollama_base_url,
        ollama_context_length=options.ollama_context_length,
        check_only=options.check_only,
    )
    pre_results, base_context = run_pre_pipeline(base_context)
    pre_elapsed = time.monotonic() - pre_start

    for r in pre_results:
        if r.status == "pass":
            log.info(run_id, f"readiness: {r.name} → pass ({round(r.elapsed_seconds, 3)}s)")
        elif r.status == "fail":
            diag = r.diagnostic
            if diag is not None:
                # T052: route through diagnostics.format_diagnostic_line so the
                # stderr text matches the closed CheckDiagnostic shape and the
                # JSON-side diagnostic object content exactly.
                log.error(run_id, diagnostics.format_diagnostic_line(r.name, diag))

    # Short-circuit on readiness failure (or --check-only completion).
    pre_passed = overall_passed(pre_results)
    if not pre_passed:
        failing_check = first_failing_check_name(pre_results)
        # Under --check-only, checks 7-8 are skipped; otherwise also skipped after a fail.
        post_results = run_post_pipeline(base_context, pre_results)
        readiness = _assemble_readiness_summary(pre_results, post_results, pre_elapsed)
        report = _build_report(
            options=options,
            voter_ref=voter_ref,
            readiness=readiness,
            runtime_outcome=None,
            stalled_phase=None,
            failure_kind="readiness-failed",
            failing_check_name=failing_check,
            phase_timings=_empty_phase_timings(),
            total_runtime_seconds=None,
            artifact_paths=None,
            quality_status=None,
            quality_status_source=None,
            cpu_fallback=_all_null_cpu_fallback(),
            diagnostic=(
                f"readiness check '{failing_check}' failed"
                if failing_check
                else "readiness failed"
            ),
            run_id=run_id,
        )
        _emit_report(report)
        return int(ExitCode.READINESS_FAILED)

    if options.check_only:
        # --check-only success path: emit stable-shape report with all
        # runtime/quality/timing/artifact fields null. Q2 success stderr signal.
        post_results = run_post_pipeline(base_context, pre_results)
        readiness = _assemble_readiness_summary(pre_results, post_results, pre_elapsed)
        log.info(run_id, f"readiness passed ({round(pre_elapsed, 3)}s)")
        report = _build_report(
            options=options,
            voter_ref=voter_ref,
            readiness=readiness,
            runtime_outcome=None,
            stalled_phase=None,
            failure_kind=None,
            failing_check_name=None,
            phase_timings=_empty_phase_timings(),
            total_runtime_seconds=None,
            artifact_paths=None,
            quality_status=None,
            quality_status_source=None,
            cpu_fallback=_all_null_cpu_fallback(),
            diagnostic=None,
            run_id=run_id,
        )
        # Under --check-only, document_folder is null per FR-018.
        report = dataclasses.replace(report, document_folder=None)
        _emit_report(report)
        return int(ExitCode.SUCCESS)

    # ------------------------------------------------------------------
    # 4. Eager-delete the 4 canonical artifacts (FR-017).
    # ------------------------------------------------------------------
    assert canonical_folder is not None  # established by --check-only branch above
    try:
        safe_eager_delete(canonical_folder, CANONICAL_ARTIFACT_BASENAMES)
        log.info(
            run_id,
            f"eager-delete: 4 artifacts removed from {canonical_folder}",
        )
    except EagerDeleteError as exc:
        log.error(run_id, f"invalid input: {exc}")
        readiness = _assemble_readiness_summary(pre_results, [], pre_elapsed)
        report = _build_report(
            options=options,
            voter_ref=voter_ref,
            readiness=readiness,
            runtime_outcome=None,
            stalled_phase=None,
            failure_kind="invalid-input",
            failing_check_name=None,
            phase_timings=_empty_phase_timings(),
            total_runtime_seconds=None,
            artifact_paths=None,
            quality_status=None,
            quality_status_source=None,
            cpu_fallback=_all_null_cpu_fallback(),
            diagnostic=f"eager-delete: {exc}",
            run_id=run_id,
        )
        _emit_report(report)
        return int(ExitCode.INVALID_INPUT)

    # ------------------------------------------------------------------
    # 5. Pipeline phases (in-process composition via PipelineComposer).
    # ------------------------------------------------------------------
    composer = options.composer or _DefaultPipelineComposer()
    phase_timings = PhaseTimings()
    runtime_outcome: Optional[RuntimeOutcome] = None
    stalled_phase: Optional[StalledPhase] = None
    failure_kind: Optional[FailureKind] = None
    diagnostic_msg: Optional[str] = None

    pipeline_start = time.monotonic()
    # Per-phase timing closure
    timings: dict[str, Optional[float]] = {
        "preprocess": None,
        "extraction": None,
        "routing": None,
        "final_payload": None,
    }

    def _run_phase(phase: StalledPhase, fn) -> None:
        nonlocal runtime_outcome, stalled_phase, failure_kind, diagnostic_msg
        if runtime_outcome is not None:
            return  # earlier phase already failed; skip
        log.info(run_id, f"phase: {phase} (starting)")
        phase_start = time.monotonic()
        try:
            fn()
        except PipelineUnavailable as exc:
            timings[phase] = time.monotonic() - phase_start
            runtime_outcome = f"failed_at_{phase}"  # type: ignore[assignment]
            failure_kind = "pipeline-runtime-error"
            diagnostic_msg = str(exc)
            log.error(run_id, f"phase {phase} failed: {exc}")
        except TimeoutError:
            # SIGALRM-triggered timeout — record the in-flight phase wall-clock
            # and let the outer `except TimeoutError` handle the
            # `runtime_outcome: "timeout"` mapping. Re-raising here is REQUIRED:
            # without it the generic `except Exception` below would catch
            # TimeoutError (TimeoutError → OSError → Exception) and mis-map it
            # to `failed_at_<phase>` + exit 4 instead of the FR-008/FR-020
            # `timeout` outcome + exit 3.
            timings[phase] = time.monotonic() - phase_start
            raise
        except Exception as exc:  # noqa: BLE001 — orchestrator catches all
            timings[phase] = time.monotonic() - phase_start
            runtime_outcome = f"failed_at_{phase}"  # type: ignore[assignment]
            failure_kind = "pipeline-runtime-error"
            diagnostic_msg = f"{type(exc).__name__}: {exc}"
            log.error(run_id, f"phase {phase} failed: {exc}")
        else:
            timings[phase] = time.monotonic() - phase_start
            log.info(
                run_id, f"phase: {phase} → {round(timings[phase] or 0, 3)}s"
            )

    # Install the 600 s SIGALRM monitor for the full pipeline window.
    timeout_observed = {"flag": False, "phase": None}

    def _on_timeout(signum, frame):  # noqa: ARG001
        timeout_observed["flag"] = True
        # Identify the most recent in-flight phase (the last one without a
        # timing recorded).
        for p in ("preprocess", "extraction", "routing", "final_payload"):
            if timings[p] is None:
                timeout_observed["phase"] = p
                break
        raise TimeoutError(
            f"pipeline runtime exceeded {options.bounded_timeout_seconds}s budget"
        )

    previous_handler = signal.getsignal(signal.SIGALRM) if hasattr(signal, "SIGALRM") else None
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _on_timeout)
        signal.alarm(options.bounded_timeout_seconds)

    try:
        _run_phase("preprocess", lambda: composer.preprocess(canonical_folder, options.preset))
        _run_phase("extraction", lambda: composer.extract(canonical_folder, voter_ref))
        _run_phase("routing", lambda: composer.route(canonical_folder))
        _run_phase("final_payload", lambda: composer.assemble(canonical_folder))
    except TimeoutError as exc:
        # SIGALRM-triggered timeout: pinpoint which phase was running.
        runtime_outcome = "timeout"
        stalled_phase = timeout_observed.get("phase")  # type: ignore[assignment]
        failure_kind = "pipeline-runtime-timeout"
        diagnostic_msg = str(exc)
        log.error(run_id, f"pipeline runtime timeout — stalled phase: {stalled_phase}")
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)

    pipeline_elapsed = time.monotonic() - pipeline_start
    phase_timings = PhaseTimings(
        preprocess=timings["preprocess"],
        extraction=timings["extraction"],
        routing=timings["routing"],
        final_payload=timings["final_payload"],
    )

    # ------------------------------------------------------------------
    # 6. Post-pipeline readiness (schema validation, runtime timeout report).
    # ------------------------------------------------------------------
    post_ctx = dataclasses.replace(
        base_context,
    )
    # Attach the timeout-observed flag via attribute (the runtime_timeout
    # check reads it via getattr).
    object.__setattr__(post_ctx, "runtime_timeout_observed", timeout_observed["flag"])
    object.__setattr__(post_ctx, "stalled_phase", timeout_observed.get("phase"))

    post_results = run_post_pipeline(post_ctx, pre_results)

    # Schema-validation failure rewrites runtime_outcome to failed_at_final_payload
    # with failure_kind = artifact-schema-validation-failed (per FR-021 exit 5).
    for r in post_results:
        if r.name == "artifact-schema-validation" and r.status == "fail":
            runtime_outcome = "failed_at_final_payload"
            failure_kind = "artifact-schema-validation-failed"
            if r.diagnostic is not None:
                diagnostic_msg = (
                    f"artifact-schema-validation failed: {r.diagnostic.observed!r}"
                )

    if runtime_outcome is None:
        runtime_outcome = "success"

    full_readiness_elapsed = pre_elapsed + sum(r.elapsed_seconds for r in post_results)
    readiness = _assemble_readiness_summary(pre_results, post_results, full_readiness_elapsed)

    artifact_paths: Optional[list[str]] = None
    if canonical_folder is not None:
        artifact_paths = [
            str(canonical_folder / b) for b in CANONICAL_ARTIFACT_BASENAMES
        ]

    # ------------------------------------------------------------------
    # 6b. Post-run CPU-fallback interrogation (US4 T064, R-023.15).
    #     Runs on every pipeline path — success or failure — to enforce SC-004.
    # ------------------------------------------------------------------
    cpu_fallback = _all_null_cpu_fallback()
    if runtime_outcome is not None:  # pipeline ran (success or failure)
        outcome = cpu_fallback_mod.interrogate(
            ollama_base_url=options.ollama_base_url,
            expected_model=voter_ref.model_name,
        )
        cpu_fallback = CPUFallbackDetection(
            ollama_post_run=outcome.ollama_post_run,
            paddle_post_run=outcome.paddle_post_run,
            pre_run_ollama_snapshot=outcome.pre_run_ollama_snapshot,
            post_run_ollama_snapshot=outcome.post_run_ollama_snapshot,
        )
        # SC-004 enforcement: silent CPU fallback → rewrite outcome.
        if outcome.fell_back and runtime_outcome == "success":
            runtime_outcome = "failed_at_extraction"
            failure_kind = "cpu-fallback-detected"
            diagnostic_msg = (
                "post-run interrogation detected CPU fallback "
                f"(ollama={outcome.ollama_post_run}, paddle={outcome.paddle_post_run})"
            )
            log.error(run_id, diagnostic_msg)
        elif outcome.unreachable and runtime_outcome == "success" and failure_kind is None:
            failure_kind = "post-run-interrogation-unreachable"
            log.warn(
                run_id,
                "post-run interrogation could not confirm GPU placement "
                f"(ollama={outcome.ollama_post_run}, paddle={outcome.paddle_post_run})",
            )

    # ------------------------------------------------------------------
    # 7. Quality status derivation (T060 + T063 wiring).
    #    Computed only on the success path (bi-conditional invariant 5).
    # ------------------------------------------------------------------
    quality_status: Optional[QualityStatus] = None
    quality_status_source: Optional[QualityStatusSource] = None
    if runtime_outcome == "success":
        # Optional evaluator augmentation (T063, R-023.13).
        evaluator_verdict: Optional[EvaluatorVerdict] = None
        if options.with_evaluator:
            eval_result = evaluator_mod.invoke_evaluator(canonical_folder)
            if eval_result.sidecar_missing:
                log.warn(
                    run_id,
                    "--with-evaluator: semantic_table_truth.json not found in "
                    f"{canonical_folder}; skipping evaluator",
                )
            elif eval_result.subprocess_failed:
                log.warn(
                    run_id,
                    "--with-evaluator: evaluator subprocess failed with exit "
                    f"{eval_result.subprocess_exit_code}; "
                    "falling back to gate-derived quality_status",
                )
            elif eval_result.semantic_table_quality_passed is not None:
                evaluator_verdict = EvaluatorVerdict(
                    semantic_table_quality_passed=eval_result.semantic_table_quality_passed,
                )

        # Read preprocessing run_summary if the composer attached it.
        run_summary = getattr(options, "_preprocess_run_summary", None)
        # Derive document_id from the canonical folder name (feature 020 convention).
        document_id = canonical_folder.name
        quality_status, quality_status_source = quality_mod.derive(
            document_folder=canonical_folder,
            document_id=document_id,
            preprocess_run_summary=run_summary,
            evaluator_result=evaluator_verdict,
        )

    # ------------------------------------------------------------------
    # 8. Final success line (Q1) before emitting the JSON report.
    # ------------------------------------------------------------------
    if runtime_outcome == "success":
        log.info(
            run_id,
            f"runtime: success / quality: {quality_status}",
        )

    report = _build_report(
        options=options,
        voter_ref=voter_ref,
        readiness=readiness,
        runtime_outcome=runtime_outcome,
        stalled_phase=stalled_phase,
        failure_kind=failure_kind,
        failing_check_name=None,
        phase_timings=phase_timings,
        total_runtime_seconds=pipeline_elapsed,
        artifact_paths=artifact_paths,
        quality_status=quality_status,
        quality_status_source=quality_status_source,
        cpu_fallback=cpu_fallback,
        diagnostic=diagnostic_msg,
        run_id=run_id,
    )
    _emit_report(report)
    return int(_exit_code_for(runtime_outcome, failure_kind))
