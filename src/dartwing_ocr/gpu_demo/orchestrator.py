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
        # M2: phase names MUST be StalledPhase literals ("extraction" not "extract").
        raise PipelineUnavailable("extraction", "see preprocess")

    def route(self, document_folder: Path) -> Any:
        # M2: "routing" matches the StalledPhase Literal.
        raise PipelineUnavailable("routing", "see preprocess")

    def assemble(self, document_folder: Path) -> Any:
        # M2: "final_payload" matches the StalledPhase Literal.
        raise PipelineUnavailable("final_payload", "see preprocess")


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


@dataclass
class _RunState:
    """Mutable per-run state captured outside the frozen :class:`OrchestratorOptions`.

    Holds values that originate inside the run (composer return values, cached
    side-channel data) and need to be read later by quality derivation,
    cpu-fallback interrogation, etc. Triage B3: prior to this container, the
    orchestrator tried to publish ``_preprocess_run_summary`` via
    ``getattr(frozen_options, ...)`` — which is structurally ``None`` for a
    frozen dataclass and silently broke SC-004's gate-derived quality status.
    """

    preprocess_run_summary: Optional[dict[str, Any]] = None
    pre_run_ollama_snapshot: Optional[dict[str, Any]] = None


def _extract_pre_run_snapshot(
    cached_api_ps_body: Any,
    model_name: str,
) -> Optional[dict[str, Any]]:
    """Pull the matching model entry from the cached /api/ps body.

    M3/K4 (triage / R-023.15): the Ollama reachability check publishes the
    full ``/api/ps`` response body via ``ReadinessContext.cached_api_ps_body``.
    The CPU-fallback probe receives the matching model entry as its
    ``pre_run_snapshot`` so the pre-vs-post diff is computable and the
    snapshot is echoed back into the emitted report.

    Returns ``None`` if the cached body is absent, malformed, or doesn't
    contain a matching entry.
    """
    if not isinstance(cached_api_ps_body, dict):
        return None
    models = cached_api_ps_body.get("models")
    if not isinstance(models, list):
        return None
    for entry in models:
        if isinstance(entry, dict) and entry.get("name") == model_name:
            return entry
    return None


def _extract_run_summary(result: Any) -> Optional[dict[str, Any]]:
    """Pull a ``run_summary`` payload out of a composer phase return value.

    The composer protocol's return is typed ``Any`` so both legacy path-only
    returns (e.g. ``Path``) and richer dict/object returns are accepted. A
    real workstation composer should return either:

    - a ``dict`` with a ``"run_summary"`` key, or
    - an object whose ``.run_summary`` attribute is a ``dict``.

    Anything else (including ``None`` or a bare ``Path``) is ignored — the
    quality-status derivation then falls back to reading the persisted
    ``run_summary.json`` on disk when the composer doesn't expose one.
    """
    if isinstance(result, dict):
        rs = result.get("run_summary")
        return rs if isinstance(rs, dict) else None
    rs = getattr(result, "run_summary", None)
    return rs if isinstance(rs, dict) else None


class _InvalidEnvVarError(ValueError):
    """Raised by :func:`_build_options_from_args` when an env var is malformed.

    R2-5 (round-2 triage): ``int(os.environ["OLLAMA_CONTEXT_LENGTH"])`` raises
    ``ValueError`` for non-numeric values (e.g. ``"2k"``). Previously this
    propagated past ``run()`` and prevented any DemoRunReport from being
    emitted — violating FR-019's always-emit invariant. Caught explicitly so
    we can map to a clean exit-2 ``invalid-input`` outcome with a useful
    diagnostic.
    """


def _build_options_from_args(args: argparse.Namespace) -> OrchestratorOptions:
    raw_ctx = os.environ.get(
        "OLLAMA_CONTEXT_LENGTH", str(DEFAULT_OLLAMA_CONTEXT_LENGTH)
    )
    try:
        ctx_length = int(raw_ctx)
    except (TypeError, ValueError) as exc:
        raise _InvalidEnvVarError(
            f"OLLAMA_CONTEXT_LENGTH must be an integer; got {raw_ctx!r}"
        ) from exc
    return OrchestratorOptions(
        check_only=bool(args.check_only),
        document_folder=Path(args.document_folder),
        voter_config_override=Path(args.voter_config) if args.voter_config else None,
        preset=str(args.preset),
        with_evaluator=bool(args.with_evaluator),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        ollama_context_length=ctx_length,
    )


_LOCALHOST_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})


class _InvalidOllamaBaseURL(ValueError):
    """Raised by :func:`_validate_ollama_base_url` when the URL is unusable.

    Triage B5 / R-023.14: ``OLLAMA_BASE_URL`` MUST be validated before the
    readiness phase so a malformed value surfaces as exit 2 (``invalid-input``)
    with a clear diagnostic, not an opaque ``ConnectError`` mid-readiness.
    """


def _validate_ollama_base_url(url: str) -> tuple[str, Any]:
    """Validate ``OLLAMA_BASE_URL`` per R-023.14 and return ``(trimmed, parsed)``.

    Required behavior:

    - Parse via :func:`urllib.parse.urlparse`.
    - Scheme MUST be ``http`` or ``https``.
    - Host MUST be non-empty.
    - Userinfo (``user``/``password`` components) MUST be empty — R2-8
      (round-2 triage): credentials in OLLAMA_BASE_URL would otherwise echo
      into the INFO stderr line, JSON report, and any HTTP request.
    - Invalid syntax raises :class:`_InvalidOllamaBaseURL`; the caller maps
      this to ``failure_kind = "invalid-input"`` + exit 2.

    Non-localhost hosts are valid; the caller emits an ``INFO`` stderr line
    when the parsed host is not in :data:`_LOCALHOST_HOSTS`.

    R2-9 (round-2 triage): the function now returns the parsed result
    alongside the trimmed string, so the caller doesn't re-import + re-parse.
    """
    from urllib.parse import urlparse

    if not isinstance(url, str) or not url.strip():
        raise _InvalidOllamaBaseURL("OLLAMA_BASE_URL is empty")
    candidate = url.strip()
    try:
        parsed = urlparse(candidate)
    except ValueError as exc:
        raise _InvalidOllamaBaseURL(f"OLLAMA_BASE_URL parse error: {exc}") from exc
    if parsed.scheme not in ("http", "https"):
        raise _InvalidOllamaBaseURL(
            f"OLLAMA_BASE_URL scheme must be http or https; got {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise _InvalidOllamaBaseURL(
            f"OLLAMA_BASE_URL has no host component: {candidate!r}"
        )
    if parsed.username or parsed.password:
        raise _InvalidOllamaBaseURL(
            "OLLAMA_BASE_URL must not contain userinfo (user:pass@); "
            "credentials would be echoed into stderr and the JSON report"
        )
    return candidate, parsed


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
    """Write the single-line JSON DemoRunReport to stdout.

    R2-4 (round-2 triage): FR-019 requires that a DemoRunReport line ALWAYS
    appears on stdout, on every code path. A pathological value somewhere in
    the report (e.g. a circular reference inside ``CheckDiagnostic.observed``
    that ``json.dumps`` cannot serialize) would previously raise out of
    ``run()`` with no emission. Guard the serialization so any such failure
    falls back to a minimal-but-shape-stable error line carrying the run_id
    and the closed-enum ``failure_kind`` set the operator needs to triage.
    """
    try:
        sys.stdout.write(to_json_line(report))
    except (TypeError, ValueError, RecursionError) as exc:
        fallback = (
            '{"kind":"demo_run_report","schema_version":'
            f'"{DEMO_REPORT_SCHEMA_VERSION}","run_id":"{report.run_id}",'
            '"runtime_outcome":null,"failure_kind":"invalid-input",'
            f'"diagnostic":"report serialization failed: {type(exc).__name__}"'
            "}\n"
        )
        sys.stdout.write(fallback)
    sys.stdout.flush()


def _format_document_folder_for_report(options: OrchestratorOptions) -> Optional[str]:
    """Return the ``document_folder`` value for the JSON report.

    Triage M1/K5: ``data-model.md §1`` requires the *attempted* path to be
    captured on invalid-input outcomes (e.g. ``--document-folder /no-such-dir``)
    so operators can triage which path was rejected. ``--check-only`` is the
    only outcome that legitimately yields ``null`` here.

    - ``--check-only``: always ``None``.
    - Folder exists: emit the canonicalized absolute path.
    - Folder doesn't exist: emit the raw operator-supplied path so the
      invalid-input diagnostic is paired with the path that was attempted.
    """
    if options.check_only:
        return None
    try:
        if options.document_folder.exists():
            return str(options.document_folder.resolve())
    except OSError:
        # Falls through to the raw-path branch on weird FS states.
        pass
    return str(options.document_folder)


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
        document_folder=_format_document_folder_for_report(options),
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
    run_id = new_run_id()
    # R2-5 (round-2 triage): build options inside a guard so a malformed env
    # var (e.g. OLLAMA_CONTEXT_LENGTH="2k") becomes exit 2 invalid-input
    # WITH an emitted DemoRunReport per FR-019's always-emit invariant.
    try:
        options = _build_options_from_args(args)
    except _InvalidEnvVarError as exc:
        # Need a minimal `options` to fit the report shape — synthesize defaults
        # from argparse only (env-var fields are the ones that failed).
        fallback_options = OrchestratorOptions(
            check_only=bool(args.check_only),
            document_folder=Path(args.document_folder),
            voter_config_override=Path(args.voter_config) if args.voter_config else None,
            preset=str(args.preset),
            with_evaluator=bool(args.with_evaluator),
        )
        log.error(run_id, f"invalid input: {exc}")
        report = _build_report(
            options=fallback_options,
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
            diagnostic=str(exc),
            run_id=run_id,
        )
        _emit_report(report)
        return int(ExitCode.INVALID_INPUT)

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
    # 1b. OLLAMA_BASE_URL validation (R-023.14, triage B5). Invalid URL →
    #     exit 2 invalid-input before any readiness phase runs. Non-localhost
    #     hosts emit an INFO line so operators have a paper trail.
    # ------------------------------------------------------------------
    try:
        trimmed_url, parsed_url = _validate_ollama_base_url(options.ollama_base_url)
    except _InvalidOllamaBaseURL as exc:
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
            diagnostic=str(exc),
            run_id=run_id,
        )
        _emit_report(report)
        return int(ExitCode.INVALID_INPUT)
    # R2-9 (round-2 triage): persist the trimmed URL back into options so
    # downstream readiness/probe code sees the canonical value (operators
    # who set OLLAMA_BASE_URL="  http://x:11434  " would otherwise carry the
    # whitespace into f"{base_url.rstrip('/')}/api/ps" — non-fatal but ugly).
    options = dataclasses.replace(options, ollama_base_url=trimmed_url)
    if parsed_url.hostname not in _LOCALHOST_HOSTS:
        log.info(
            run_id,
            f"using non-localhost Ollama base URL: {trimmed_url}",
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
    # B3 mutable RunState (composer-published values; see _RunState docstring).
    run_state = _RunState()
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
            phase_result = fn()
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
            # B3: capture composer return-value into mutable RunState so quality
            # derivation can read the preprocessing run_summary without going
            # through the frozen-dataclass channel.
            if phase == "preprocess":
                rs = _extract_run_summary(phase_result)
                if rs is not None:
                    run_state.preprocess_run_summary = rs
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
        # SIGALRM-triggered timeout: pinpoint which phase was running. R2-3
        # (round-2 triage): mask SIGALRM via pthread_sigmask BEFORE touching
        # any state so a queued alarm cannot fire mid-assignment and re-raise
        # past run(). Wrap the assignment + log body in an extra try/except
        # belt-and-suspenders for platforms that don't expose pthread_sigmask.
        _previous_sigmask = None
        if hasattr(signal, "pthread_sigmask") and hasattr(signal, "SIGALRM"):
            try:
                _previous_sigmask = signal.pthread_sigmask(
                    signal.SIG_BLOCK, {signal.SIGALRM}
                )
            except (OSError, ValueError):
                _previous_sigmask = None
        if hasattr(signal, "SIGALRM"):
            try:
                signal.alarm(0)
            except TimeoutError:
                pass
        try:
            runtime_outcome = "timeout"
            stalled_phase = timeout_observed.get("phase")  # type: ignore[assignment]
            failure_kind = "pipeline-runtime-timeout"
            diagnostic_msg = str(exc)
            log.error(
                run_id,
                f"pipeline runtime timeout — stalled phase: {stalled_phase}",
            )
        except TimeoutError:
            pass  # late-arriving alarm; state is already partially set
        finally:
            if _previous_sigmask is not None:
                try:
                    signal.pthread_sigmask(signal.SIG_SETMASK, _previous_sigmask)
                except (OSError, ValueError):
                    pass
    finally:
        # B4: wrap both alarm-cancel and handler-restore in try/except so a
        # SIGALRM that fires between phase return and `signal.alarm(0)` (or
        # inside this finally block) cannot leak an unhandled TimeoutError
        # past run() — FR-019 requires an emitted DemoRunReport on every path.
        if hasattr(signal, "SIGALRM"):
            try:
                signal.alarm(0)
            except TimeoutError:
                pass  # late-arriving alarm; cleanup wins
            if previous_handler is not None:
                try:
                    signal.signal(signal.SIGALRM, previous_handler)
                except TimeoutError:
                    pass

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
    # R2-11 (round-2 triage): the timeout state used to be injected via
    # object.__setattr__ on a frozen=True dataclass — the same anti-pattern
    # B3 retired for `_preprocess_run_summary`. Promote to proper Optional
    # fields on ReadinessContext and use dataclasses.replace.
    post_ctx = dataclasses.replace(
        base_context,
        runtime_timeout_observed=timeout_observed["flag"],
        stalled_phase=timeout_observed.get("phase"),
    )

    post_results = run_post_pipeline(post_ctx, pre_results)

    # Schema-validation failure rewrites runtime_outcome to failed_at_final_payload
    # with failure_kind = artifact-schema-validation-failed (per FR-021 exit 5).
    # Guard: only rewrite when the pipeline ran to completion. On an earlier
    # phase failure (e.g. failed_at_extraction), the missing routing/final
    # artifacts will trip check 7 as a side-effect; rewriting here would mask
    # the true cause and downgrade exit 4 → exit 5.
    if runtime_outcome is None:
        for r in post_results:
            if r.name == "artifact-schema-validation" and r.status == "fail":
                runtime_outcome = "failed_at_final_payload"
                failure_kind = "artifact-schema-validation-failed"
                if r.diagnostic is not None:
                    diagnostic_msg = (
                        f"artifact-schema-validation failed: {r.diagnostic.observed!r}"
                    )
                # R2-15 (round-2 triage): exit 5 previously had no stderr
                # line of record — operators had to read the JSON line to
                # learn what failed. Emit an ERROR line so `grep ERROR
                # demo.stderr` works as the stderr-cheat-sheet entry-point.
                log.error(
                    run_id,
                    "artifact-schema-validation failed; see JSON "
                    "readiness.checks[name=artifact-schema-validation].diagnostic",
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
    #     Runs on success + timeout + schema-fail paths to enforce SC-004.
    #     R2-16 (round-2 triage): skipped on pipeline-runtime-error so the
    #     stderr narrative isn't muddied with an extra WARN/INFO line about
    #     device health after the operator already saw the phase-fail ERROR.
    # ------------------------------------------------------------------
    cpu_fallback = _all_null_cpu_fallback()
    _should_probe_devices = (
        runtime_outcome is not None
        and failure_kind != "pipeline-runtime-error"
    )
    if _should_probe_devices:
        # M3/K4: thread the readiness-cached /api/ps body's matching model
        # entry into the probe so pre_run_ollama_snapshot is populated in
        # the emitted report and the pre-vs-post diff is actually computed.
        pre_run_snapshot = _extract_pre_run_snapshot(
            getattr(base_context, "cached_api_ps_body", None),
            voter_ref.model_name,
        )
        outcome = cpu_fallback_mod.interrogate(
            ollama_base_url=options.ollama_base_url,
            expected_model=voter_ref.model_name,
            pre_run_snapshot=pre_run_snapshot,
        )
        cpu_fallback = CPUFallbackDetection(
            ollama_post_run=outcome.ollama_post_run,
            paddle_post_run=outcome.paddle_post_run,
            pre_run_ollama_snapshot=outcome.pre_run_ollama_snapshot,
            post_run_ollama_snapshot=outcome.post_run_ollama_snapshot,
        )
        # K3 (triage / R-023.15): aggregate-budget-exceeded → prescribed WARN.
        if outcome.budget_exceeded:
            log.warn(
                run_id,
                "post-run interrogation exceeded 5s budget; "
                "CPU-fallback detection inconclusive",
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
            # K6 (triage): demo-report-schema.md requires `diagnostic` to be
            # non-null when `failure_kind` is non-null — set it here so the
            # post-run-interrogation-unreachable branch doesn't emit a
            # contradictory (failure_kind != null, diagnostic == null) report.
            diagnostic_msg = (
                "post-run interrogation could not confirm GPU placement "
                f"(ollama={outcome.ollama_post_run}, paddle={outcome.paddle_post_run})"
            )
            log.warn(run_id, diagnostic_msg)
        elif (
            runtime_outcome == "success"
            and outcome.ollama_post_run == "consistent"
            and outcome.paddle_post_run == "consistent"
        ):
            # K7 (triage): match cli-contract.md "Worked examples" stderr signal
            # so operators can confirm at a glance that post-run interrogation
            # actually corroborated GPU placement (not just that nothing failed).
            log.info(
                run_id,
                "post-run: ollama still GPU-placed; paddle still rocm_gpu",
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

        # Read preprocessing run_summary from the mutable RunState. The
        # composer's preprocess() return value is inspected by _run_phase and
        # any dict/attr named ``run_summary`` is captured here. If the
        # composer doesn't publish one, the quality module falls back to
        # reading the persisted run_summary on disk (or to a stub default).
        run_summary = run_state.preprocess_run_summary
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
