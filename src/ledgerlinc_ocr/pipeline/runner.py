"""Pipeline orchestration.

The runner executes the contiguous stage slice resolved from a
``ResolvedRunPlan`` (or, for backward compatibility, a bare
``CLIInvocation`` which is internally wrapped in a default plan).
Stages are pluggable: tests inject ``StageCallable``s directly, while
the CLI dispatches through the profile-resolution registry in
``stages.py``.

Spec FR-009 / FR-010 / FR-011 / FR-012 / FR-014. Research R-004 / R-005 /
R-006 / R-009 / R-014 / R-015. Data-model `CLIInvocation`,
`ResolvedRunPlan`, `DocumentRun`, `DocumentOutcome`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

from ledgerlinc_ocr.pipeline.exit_codes import ExitCode
from ledgerlinc_ocr.pipeline.failure_policy import FailurePolicy
from ledgerlinc_ocr.pipeline.ollama_lanes import (
    OllamaLaneEndpoints,
    resolve_endpoints,
)
from ledgerlinc_ocr.pipeline.profiles import (
    DEFAULT_PROFILES,
    STAGES,
    Stage,
    StageProfile,
    parse_profile,
)
from ledgerlinc_ocr.pipeline.slice_control import (
    ARTIFACT_FILENAME_BY_STAGE,
    ExecutionSlice,
    check_prerequisites,
    existing_outputs_in_slice,
    unusable_outputs_in_slice,
)
from ledgerlinc_ocr.pipeline.timing import (
    DocumentTimings,
    StageTiming,
    bind_current_stage_timing,
    measure_phase,
    measure_total,
)
from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.loader import load_contract_set
from ledgerlinc_ocr.validator.report import ArtifactName

RESERVED_ARTIFACT_NAMES: tuple[str, ...] = (
    "preprocess_output.json",
    "edge_extraction_output.json",
    "routing_decision.json",
    "final_structured_payload.json",
)

OFF_LIMITS_NAMES: tuple[str, ...] = (
    "evaluation_document.json",
    "consensus_output.json",
    "votes",
)

_FILENAME_TO_ARTIFACT: dict[str, ArtifactName] = {
    "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
    "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision.json": ArtifactName.ROUTING_DECISION,
    "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
}

_STAGE_TO_FILENAME: dict[Stage, str] = dict(ARTIFACT_FILENAME_BY_STAGE)
_FILENAME_TO_STAGE: dict[str, Stage] = {
    v: k for k, v in _STAGE_TO_FILENAME.items()
}

# Stage names as they appear on the existing ``Stage`` literal in
# exit_codes.py (these are the values used in StructuredFailureRecord.stage
# when a stage's adapter raises). We keep them aligned so the cold-mode
# path emits exactly the same record shape as 002-cli-contract.
_STAGE_FAILURE_NAMES: dict[Stage, str] = {
    "preprocess": "preprocess",
    "extract": "extraction",
    "routing": "routing",
    "final_payload": "final_payload",
}


@dataclass
class CLIInvocation:
    """Per-invocation parameters shared across cold and warm modes.

    The pre-011 fields (``input_pdf`` ... ``timeout``) are preserved
    verbatim. New optional fields carry the additional CPU/Jetson lane
    URL overrides so the legacy single-document call site can wrap
    itself in a default ``ResolvedRunPlan``.
    """
    input_pdf: Path
    destination_folder: Path
    document_id: str
    overwrite: bool
    pipeline_version: str | None
    policy_version: str
    contract_set_version: str
    ollama_url: str
    log_level: str
    timeout: int
    ollama_cpu_url: str | None = None
    ollama_jetson_url: str | None = None
    # Feature 016 (Copilot PR #24 round 3): CLI-intent flag set by the
    # cold-mode `_run_cold` after resolving `--gpu-warmup` /
    # `LEDGERLINC_GPU_WARMUP=1` against the resolved preprocess profile
    # lane. **Diagnostic only — no longer threaded through the
    # preprocessing adapter.** Runtime warmup is driven by the hoisted
    # `pipeline.run_warmup_if_active()` call in `_run_cold` BEFORE the
    # runner dispatches any stage, so warmup duration is excluded from
    # `phase_timings.total.seconds` per FR-007 / SC-004. Warm-corpus
    # mode reads `--gpu-warmup` directly from `args` in
    # `pipeline.corpus_run` and does not touch this field.
    warmup: bool = False
    # Feature 017 (review CRITICAL fix): resolved preset identifier
    # strings threaded from `pipeline/cli.py::main` after argv parse +
    # cross-profile warn-and-proceed. `None` means either the operator
    # did not pass the flag or the warn-and-proceed branch nulled the
    # value (non-GPU profile). Read by `_run_cold_warmup_if_active` to
    # forward to `run_warmup_if_active` and by the cold-path stage
    # dispatcher to derive the per-stage Invocation's preset values.
    module_set_id: str | None = None
    det_rec_variant_id: str | None = None
    # Feature 018 (T006a): same shape and threading discipline as
    # feature 017's `module_set_id` / `det_rec_variant_id` above. `None`
    # means either the operator did not pass `--raster-profile` /
    # `--region-strategy` or the warn-and-proceed branch nulled the
    # value (non-GPU profile per FR-014). US1 (T009/T010) writes the
    # resolved `RasterProfile.name` here on GPU runs;
    # US2 (T019/T020) writes the resolved `RegionStrategy.name` and
    # increments the per-run fallback accumulator that lands on
    # `RunSummary.region_strategy_fallback_count`.
    raster_profile_id: str | None = None
    region_strategy_id: str | None = None
    # Feature 018: mutable per-document signal surfaced by the live
    # preprocessing adapter after `preprocessing.pipeline.run()` returns.
    # Warm-corpus mode reads it to aggregate
    # `RunSummary.region_strategy_fallback_count`.
    region_strategy_fallback_fired: bool = False
    # Feature 019 (T006a / T009 / T011 / T021 / T022): same shape and
    # threading discipline as feature 017/018's identifier fields above.
    # `None` means either the operator did not pass `--preprocess-strategy`
    # or the warn-and-proceed branch nulled the value (non-GPU profile per
    # FR-013). US1 (T009 / T011) writes the resolved `PreprocessStrategy.name`
    # here on GPU runs; US3 (T021 / T022) flips `ocr_only_fallback_fired`
    # to True per-document when the FR-005 combined two-threshold check
    # triggers fallback to `ppstructurev3` on that document; warm-corpus
    # mode aggregates the flag into `RunSummary.ocr_only_fallback_count`.
    preprocess_strategy_id: str | None = None
    ocr_only_fallback_fired: bool = False


StageCallable = Callable[[CLIInvocation, dict[str, Any]], Any]


RunMode = Literal["cold_single_document", "warm_corpus"]


@dataclass
class ResolvedRunPlan:
    """Aggregate of all argument-resolution outputs.

    The runner takes one ``ResolvedRunPlan`` and executes the configured
    slice for either a single per-document folder (cold mode) or a list
    of folders driven by ``--documents-file`` (warm mode). The
    underlying ``CLIInvocation`` is preserved so existing helpers that
    accept it continue to work.
    """
    mode: RunMode
    cli_invocation: CLIInvocation
    profiles: dict[Stage, StageProfile]
    slice_: ExecutionSlice
    ollama_endpoints: OllamaLaneEndpoints
    failure_policy: FailurePolicy
    stack_preset_name: str | None
    documents: tuple[Path, ...]


def make_default_plan(invocation: CLIInvocation) -> ResolvedRunPlan:
    """Wrap a legacy ``CLIInvocation`` in a default cold-mode run plan.

    Used by tests and the legacy single-document call site (``Runner.run``
    accepting a bare invocation) to apply the current default profiles when no
    per-stage profile flags or stack preset is supplied.
    """
    profiles: dict[Stage, StageProfile] = {
        stage: parse_profile(stage, raw)
        for stage, raw in DEFAULT_PROFILES.items()
    }
    slice_ = ExecutionSlice(start_at="preprocess", stop_after="final_payload")
    endpoints = resolve_endpoints(
        gpu_flag=invocation.ollama_url,
        cpu_flag=invocation.ollama_cpu_url,
        jetson_flag=invocation.ollama_jetson_url,
    )
    return ResolvedRunPlan(
        mode="cold_single_document",
        cli_invocation=invocation,
        profiles=profiles,
        slice_=slice_,
        ollama_endpoints=endpoints,
        failure_policy=FailurePolicy(mode="fail-fast"),
        stack_preset_name=None,
        documents=(invocation.destination_folder,),
    )


@dataclass
class DocumentOutcome:
    """The outcome of executing one ``DocumentRun`` (data-model)."""
    status: Literal["success", "failure"]
    exit_code: ExitCode
    failed_stage: str = ""
    message: str = ""
    artifacts_written: tuple[Path, ...] = ()


@dataclass
class DocumentRun:
    """Per-document execution context the runner tracks during a run."""
    folder: Path
    document_id: str
    timings: DocumentTimings = field(default_factory=DocumentTimings)
    outcome: DocumentOutcome | None = None


@dataclass
class RunResult:
    """Backward-compatible result shape returned by ``Runner.run``."""
    exit_code: ExitCode
    artifacts_written: list[Path] = field(default_factory=list)
    stage: str = "schema_validation"
    message: str = ""
    routing_decision: dict[str, Any] | None = None
    timings: DocumentTimings | None = None


@dataclass(frozen=True)
class StageRunOutput:
    """Stage adapter result for adapters that already wrote their artifact."""

    payload: dict[str, Any]
    artifact_path: Path
    already_written: bool = True


_STAGE_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("preprocess_output.json", "preprocess"),
    ("edge_extraction_output.json", "extraction"),
    ("routing_decision.json", "routing"),
    ("final_structured_payload.json", "final_payload"),
)

# Per-stage compute-phase key vocabulary (R-009 / FR-027). The runner
# measures the adapter call as the stage's compute phase and the
# subsequent disk write as ``write``. For ``preprocess`` specifically,
# the upstream PPStructureV3 module bundles rasterization, layout
# inference, and OCR inside a single ``run`` call -- the contract
# folds those into ``infer`` for this slice; future adapters that
# split rasterize/infer can record both phase keys without breaking
# consumers (R-009 phase-key absence policy).
_STAGE_COMPUTE_PHASE: dict[Stage, str] = {
    "preprocess": "infer",
    "extract": "infer",
    "routing": "compute",
    "final_payload": "compute",
}


def _format_stage_exception(
    exc: Exception, *, profile: StageProfile | None = None
) -> str:
    # Feature 016: preserve `cause_class` on the message so the cold CLI
    # can reconstruct the canonical `error: warmup failed: <cause-class>:
    # <msg>` literal stderr line without re-handling the exception object.
    from ledgerlinc_ocr.preprocessing.errors import WarmupError as _WarmupError

    if isinstance(exc, _WarmupError):
        return f"warmup failed: {exc.cause_class}: {exc}"
    if isinstance(exc, ModuleNotFoundError):
        missing = exc.name or str(exc) or type(exc).__name__
        suffix = (
            f" for selected profile {profile.raw_value}"
            if profile is not None else ""
        )
        return (
            f"missing runtime dependency{suffix}: {missing}. "
            f"Install the selected live runtime dependencies or use stub profiles."
        )
    if isinstance(exc, ImportError):
        suffix = (
            f" for selected profile {profile.raw_value}"
            if profile is not None else ""
        )
        return (
            f"could not import runtime dependency{suffix}: "
            f"{str(exc) or type(exc).__name__}. "
            f"Install the selected live runtime dependencies or use stub profiles."
        )
    return str(exc) or type(exc).__name__


def _prerequisite_failure(check: Any, timings: DocumentTimings) -> RunResult:
    if check.missing_artifact is not None:
        return RunResult(
            exit_code=ExitCode.INPUT_NOT_FOUND,
            artifacts_written=[],
            stage="prerequisite_validation",
            message=f"prerequisite artifact missing: {check.missing_artifact}",
            timings=timings,
        )
    return RunResult(
        exit_code=ExitCode.SCHEMA_VALIDATION_FAILURE,
        artifacts_written=[],
        stage="prerequisite_validation",
        message=(
            f"prerequisite artifact failed schema validation: "
            f"{check.invalid_artifact}: {check.invalid_reason}"
        ),
        timings=timings,
    )


__all__ = [
    "CLIInvocation",
    "DocumentOutcome",
    "DocumentRun",
    "OFF_LIMITS_NAMES",
    "RESERVED_ARTIFACT_NAMES",
    "ResolvedRunPlan",
    "RunMode",
    "RunResult",
    "Runner",
    "StageCallable",
    "StageRunOutput",
    "make_default_plan",
]


# Runner is implemented after all dataclasses so the file stays linear.
class Runner:
    """Stage 1 pipeline runner.

    Two ways to drive it:
      * ``Runner(...).run(invocation)``  -- legacy cold-mode entrypoint.
      * ``Runner(...).run_plan(plan)``   -- runs a single document under
        a ``ResolvedRunPlan`` (warm-corpus orchestration calls this once
        per document inside its own loop).
    """

    def __init__(
        self,
        *,
        preprocess: StageCallable | None = None,
        extraction: StageCallable | None = None,
        routing: StageCallable | None = None,
        final_payload: StageCallable | None = None,
    ) -> None:
        # Lazy import to avoid a cycle: stages.py imports nothing from
        # runner.py at module-load time.
        from ledgerlinc_ocr.pipeline.stages import (
            default_extraction,
            default_final_payload,
            default_preprocess,
            default_routing,
        )
        self._injected: dict[str, StageCallable | None] = {
            "preprocess_output.json": preprocess,
            "edge_extraction_output.json": extraction,
            "routing_decision.json": routing,
            "final_structured_payload.json": final_payload,
        }
        self._defaults: dict[str, StageCallable] = {
            "preprocess_output.json": default_preprocess,
            "edge_extraction_output.json": default_extraction,
            "routing_decision.json": default_routing,
            "final_structured_payload.json": default_final_payload,
        }

    def run(self, invocation: CLIInvocation) -> RunResult:
        """Legacy cold-mode entrypoint. Wraps ``invocation`` in a default plan."""
        plan = make_default_plan(invocation)
        return self.run_plan(plan, folder=invocation.destination_folder)

    def _check_deferred_live_profiles(
        self,
        plan: ResolvedRunPlan,
        timings: DocumentTimings,
    ) -> RunResult | None:
        from ledgerlinc_ocr.pipeline.stages import (
            DEFERRED_LIVE_PROFILES,
            _make_deferred_callable,
        )

        invocation = plan.cli_invocation
        for stage in plan.slice_.stages_in_slice:
            profile = plan.profiles[stage]
            filename = _STAGE_TO_FILENAME[stage]
            if profile.kind != "live" or self._injected.get(filename) is not None:
                continue
            key = (stage, profile.implementation, profile.lane)
            if key not in DEFERRED_LIVE_PROFILES:
                continue
            deferred = _make_deferred_callable(stage, profile)
            try:
                deferred(invocation, {})
            except Exception as exc:  # noqa: BLE001
                return RunResult(
                    exit_code=_classify_stage_exception(exc),
                    artifacts_written=[],
                    stage=_STAGE_FAILURE_NAMES[stage],
                    message=str(exc) or type(exc).__name__,
                    timings=timings,
                )
        return None

    @staticmethod
    def _check_slice_outputs_available(
        *,
        invocation: CLIInvocation,
        folder: Path,
        plan: ResolvedRunPlan,
        timings: DocumentTimings,
    ) -> RunResult | None:
        unusable = unusable_outputs_in_slice(folder, plan.slice_)
        if unusable:
            first = unusable[0]
            return RunResult(
                exit_code=ExitCode.OUTPUT_PATH_NOT_USABLE,
                artifacts_written=[],
                stage="input_validation",
                message=(
                    f"Reserved artifact path is not a regular file: "
                    f"{folder / first}"
                ),
                timings=timings,
            )
        if invocation.overwrite:
            return None
        existing = existing_outputs_in_slice(folder, plan.slice_)
        if not existing:
            return None
        first = existing[0]
        return RunResult(
            exit_code=ExitCode.OUTPUT_IN_USE,
            artifacts_written=[],
            stage="input_validation",
            message=(
                f"Reserved artifact file already exists: "
                f"{folder / first}. Pass --overwrite to replace."
            ),
            timings=timings,
        )

    @staticmethod
    def _load_prerequisite_artifacts(
        *,
        folder: Path,
        plan: ResolvedRunPlan,
        invocation: CLIInvocation,
        timings: DocumentTimings,
    ) -> tuple[dict[str, Any], RunResult | None]:
        check = check_prerequisites(
            folder=folder,
            slice_=plan.slice_,
            contract_set_version=invocation.contract_set_version,
        )
        if not check.ok:
            return {}, _prerequisite_failure(check, timings)

        produced: dict[str, Any] = {}
        for filename in plan.slice_.prerequisite_artifacts:
            try:
                produced[filename] = json.loads(
                    (folder / filename).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                return {}, RunResult(
                    exit_code=ExitCode.PROCESSING_FAILURE,
                    artifacts_written=[],
                    stage="prerequisite_validation",
                    message=f"could not read prerequisite artifact: {filename}",
                    timings=timings,
                )
        return produced, None

    def _resolve_callable_for_stage(
        self,
        *,
        stage: Stage,
        filename: str,
        plan: ResolvedRunPlan,
    ) -> StageCallable:
        injected = self._injected.get(filename)
        if injected is not None:
            return injected

        from ledgerlinc_ocr.pipeline.stages import resolve_stage_callable

        return resolve_stage_callable(
            stage=stage,
            profile=plan.profiles[stage],
            plan=plan,
        )

    def _run_stage(
        self,
        *,
        stage: Stage,
        filename: str,
        plan: ResolvedRunPlan,
        folder: Path,
        produced: dict[str, Any],
        artifacts_written: list[Path],
        timings: DocumentTimings,
    ) -> RunResult | None:
        invocation = plan.cli_invocation
        failure_stage_name = _STAGE_FAILURE_NAMES[stage]
        stage_timing = timings.get_or_create(stage)
        try:
            stage_callable = self._resolve_callable_for_stage(
                stage=stage, filename=filename, plan=plan
            )
        except Exception as exc:  # noqa: BLE001 -- contract: convert to failure
            return RunResult(
                exit_code=_classify_stage_exception(exc),
                artifacts_written=artifacts_written,
                stage=failure_stage_name,
                message=_format_stage_exception(exc, profile=plan.profiles[stage]),
                timings=timings,
            )

        with measure_total(stage_timing), bind_current_stage_timing(stage_timing):
            # Feature 015 (T021): bind_current_stage_timing exposes the
            # active StageTiming via the timing-module contextvar so live
            # preprocess adapters can record fine-grained phase keys
            # (`rasterization`, `artifact_write`) on the same map.
            with measure_phase(stage_timing, _STAGE_COMPUTE_PHASE[stage]):
                try:
                    output = stage_callable(invocation, produced)
                except Exception as exc:  # noqa: BLE001 -- contract: convert to failure
                    return RunResult(
                        exit_code=_classify_stage_exception(exc),
                        artifacts_written=artifacts_written,
                        stage=failure_stage_name,
                        message=_format_stage_exception(
                            exc, profile=plan.profiles[stage]
                        ),
                        timings=timings,
                    )
            if isinstance(output, StageRunOutput):
                payload = output.payload
                dest = output.artifact_path
                already_written = output.already_written
            else:
                payload = output
                dest = folder / filename
                already_written = False
            if already_written:
                if not dest.exists():
                    return RunResult(
                        exit_code=ExitCode.PROCESSING_FAILURE,
                        artifacts_written=artifacts_written,
                        stage=failure_stage_name,
                        message=f"stage reported written artifact missing: {dest}",
                        timings=timings,
                    )
            else:
                with measure_phase(stage_timing, "write"):
                    try:
                        dest.write_text(
                            json.dumps(payload, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )
                    except OSError as exc:
                        return RunResult(
                            exit_code=ExitCode.PROCESSING_FAILURE,
                            artifacts_written=artifacts_written,
                            stage=failure_stage_name,
                            message=f"failed to write {filename}: {exc}",
                            timings=timings,
                        )
        produced[filename] = payload
        artifacts_written.append(dest.resolve())
        return None

    @staticmethod
    def _validate_written_artifacts(
        *,
        invocation: CLIInvocation,
        artifacts_written: list[Path],
        timings: DocumentTimings,
    ) -> RunResult | None:
        contract_set = load_contract_set(invocation.contract_set_version)
        for dest in artifacts_written:
            artifact_name = _FILENAME_TO_ARTIFACT[dest.name]
            outcome = validate_artifact(
                dest, artifact_name, contract_set=contract_set
            )
            if not outcome.passed:
                first = outcome.violations[0] if outcome.violations else None
                field_path = first.field_path if first else "$"
                reason = first.reason if first else "unknown validation failure"
                return RunResult(
                    exit_code=ExitCode.SCHEMA_VALIDATION_FAILURE,
                    artifacts_written=artifacts_written,
                    stage="schema_validation",
                    message=f"{dest.name}: {field_path}: {reason}",
                    timings=timings,
                )
        return None

    @staticmethod
    def _load_routing_payload(
        *, folder: Path, plan: ResolvedRunPlan, produced: dict[str, Any]
    ) -> dict[str, Any] | None:
        routing_filename = "routing_decision.json"
        if routing_filename in produced:
            return produced[routing_filename]

        if routing_filename not in plan.slice_.prerequisite_artifacts:
            return None
        routing_path = folder / routing_filename
        if not routing_path.exists():
            return None
        try:
            return json.loads(routing_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def run_plan(
        self,
        plan: ResolvedRunPlan,
        *,
        folder: Path | None = None,
    ) -> RunResult:
        """Run one document under ``plan`` against ``folder`` (defaults to
        the plan's CLIInvocation destination).

        Honors:
          - ``plan.slice_`` (FR-009): only stages in the slice run; stages
            before it are treated as prerequisites.
          - ``check_prerequisites`` (FR-010): missing/invalid upstream
            artifacts fail before any downstream write.
          - Slice-scoped overwrite guard (FR-011): only artifacts in
            ``slice_.output_artifacts`` count as outputs-in-use.
          - Injected stage callables (FR-012): tests/programmatic callers
            override per-filename adapters without going through the
            profile registry.
          - Per-stage timing capture (FR-027 / R-009 / R-015).
        """
        invocation = plan.cli_invocation
        document_folder = folder if folder is not None else invocation.destination_folder

        timings = DocumentTimings()
        artifacts_written: list[Path] = []

        # FR-022A / R-013: any in-slice profile whose live adapter is
        # deferred to FR-034 step 4 fails fast BEFORE any artifact write
        # so a deferred extract cannot leak preprocess artifacts.
        failure = self._check_deferred_live_profiles(plan, timings)
        if failure is not None:
            return failure

        # Slice-scoped overwrite guard (FR-011 / R-006).
        failure = self._check_slice_outputs_available(
            invocation=invocation,
            folder=document_folder,
            plan=plan,
            timings=timings,
        )
        if failure is not None:
            return failure

        # Prerequisite-artifact validation (FR-010 / R-005).
        produced, failure = self._load_prerequisite_artifacts(
            folder=document_folder,
            plan=plan,
            invocation=invocation,
            timings=timings,
        )
        if failure is not None:
            return failure

        # Execute stages inside the slice in order.
        for stage in plan.slice_.stages_in_slice:
            filename = _STAGE_TO_FILENAME[stage]
            failure = self._run_stage(
                stage=stage,
                filename=filename,
                plan=plan,
                folder=document_folder,
                produced=produced,
                artifacts_written=artifacts_written,
                timings=timings,
            )
            if failure is not None:
                return failure

        # Schema validation for everything we just wrote (FR-029 stays
        # honored: same validator, same contract set, no new schemas).
        failure = self._validate_written_artifacts(
            invocation=invocation,
            artifacts_written=artifacts_written,
            timings=timings,
        )
        if failure is not None:
            return failure

        # Routing decision is the canonical signal the cold-mode stdout
        # success summary needs. If routing is inside the slice we use
        # the freshly-produced payload; otherwise we re-load the
        # pre-existing artifact so cold callers that ran a partial slice
        # still get a useful summary.
        routing_payload = self._load_routing_payload(
            folder=document_folder, plan=plan, produced=produced
        )

        return RunResult(
            exit_code=ExitCode.SUCCESS,
            artifacts_written=artifacts_written,
            stage="schema_validation",
            message="",
            routing_decision=routing_payload,
            timings=timings,
        )


def _classify_stage_exception(exc: Exception) -> ExitCode:
    """Map common adapter-raised errors to the existing ExitCode taxonomy.

    ``DeferredImplementationError`` is treated as a caller-side
    configuration error (R-013) -- exit 10, not the generic
    PROCESSING_FAILURE bucket -- because the user selected a profile
    whose live implementation is sequenced for FR-034 step 4.

    Feature 016: ``WarmupError`` raised inside the live preprocessing
    adapter on the GPU lane maps to ``ExitCode.WARMUP_FAILED`` (15) per
    FR-007 / SC-011 / `contracts/cli-contract.md` §4. The cold-mode CLI
    re-emits the canonical ``error: warmup failed: <cause-class>: <msg>``
    stderr line on this exit code (matching the warm-corpus path) and
    suppresses the generic ``StructuredFailureRecord`` JSON line.
    """
    from ledgerlinc_ocr.pipeline.stages import DeferredImplementationError
    from ledgerlinc_ocr.preprocessing.errors import WarmupError

    if isinstance(exc, DeferredImplementationError):
        return ExitCode.USAGE_ERROR
    if isinstance(exc, WarmupError):
        return ExitCode.WARMUP_FAILED
    return ExitCode.PROCESSING_FAILURE
