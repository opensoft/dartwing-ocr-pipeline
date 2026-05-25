"""Readiness runner — fixed-order execution + skip-on-upstream-fail (T033, FR-016 + FR-026).

Executes the 8 named checks in declaration order. When an earlier check
fails, every later check is marked ``"skipped"`` (status, no diagnostic).
The runner threads cached side-channel data (notably the /api/ps body) from
``ollama-reachability`` into the dependent checks via a mutable context
update so they avoid second network round-trips.

The runner is split into two execution windows:
- ``run_pre_pipeline(context)``: checks 1–6 (the ``--check-only`` set).
- ``run_post_pipeline(context, pre_results)``: checks 7–8 (skipped under
  ``--check-only`` or whenever the pipeline did not run).

The orchestrator owns the timing budget for the pre-pipeline window
(SC-007 10 s warm bound) and the 600 s pipeline-runtime budget separately.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import replace
from typing import Iterable

from dartwing_ocr.gpu_demo.enums import READINESS_CHECK_ORDER
from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessCheck,
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.readiness.interpreter import InterpreterVenvCheck
from dartwing_ocr.gpu_demo.readiness.ollama_ctx_len import OllamaContextLengthCheck
from dartwing_ocr.gpu_demo.readiness.ollama_placement import OllamaPlacementCheck
from dartwing_ocr.gpu_demo.readiness.ollama_reach import OllamaReachabilityCheck
from dartwing_ocr.gpu_demo.readiness.ollama_version import OllamaVersionCheck
from dartwing_ocr.gpu_demo.readiness.paddle_preflight import PaddleRocmPreflightCheck
from dartwing_ocr.gpu_demo.readiness.runtime_timeout import PipelineRuntimeTimeoutCheck
from dartwing_ocr.gpu_demo.readiness.schema_validation import (
    ArtifactSchemaValidationCheck,
)


def _build_pre_pipeline_checks() -> list[ReadinessCheck]:
    """Instantiate checks 1–6 in fixed order."""
    return [
        InterpreterVenvCheck(),
        PaddleRocmPreflightCheck(),
        OllamaReachabilityCheck(),
        OllamaVersionCheck(),
        OllamaPlacementCheck(),
        OllamaContextLengthCheck(),
    ]


def _build_post_pipeline_checks() -> list[ReadinessCheck]:
    """Instantiate checks 7–8 in fixed order."""
    return [
        ArtifactSchemaValidationCheck(),
        PipelineRuntimeTimeoutCheck(),
    ]


def _skipped_result(name: str) -> ReadinessResult:
    return ReadinessResult(
        name=name,  # type: ignore[arg-type]
        status="skipped",
        elapsed_seconds=0.0,
    )


def run_pre_pipeline(context: ReadinessContext) -> tuple[list[ReadinessResult], ReadinessContext]:
    """Run checks 1–6. Returns the result list AND the possibly-updated context.

    The context is updated when ``ollama-reachability`` publishes its
    /api/ps body via ``side_channel``; downstream checks 5/6 read it via
    ``context.cached_api_ps_body``.
    """
    checks = _build_pre_pipeline_checks()
    results: list[ReadinessResult] = []
    fail_reached = False
    ctx = context

    for check in checks:
        if fail_reached:
            results.append(_skipped_result(check.name))
            continue
        result = check.run(ctx)
        results.append(result)
        if result.side_channel is not None:
            ctx = dataclasses.replace(ctx, cached_api_ps_body=result.side_channel)
        if result.status == "fail":
            fail_reached = True

    return results, ctx


def run_post_pipeline(
    context: ReadinessContext,
    pre_results: Iterable[ReadinessResult],
) -> list[ReadinessResult]:
    """Run checks 7–8. Under --check-only OR if any pre-check failed, skip both."""
    pre_failed = any(r.status == "fail" for r in pre_results)
    if context.check_only or pre_failed:
        return [_skipped_result(name) for name in ("artifact-schema-validation", "pipeline-runtime-timeout")]

    checks = _build_post_pipeline_checks()
    results: list[ReadinessResult] = []
    fail_reached = False
    for check in checks:
        if fail_reached:
            results.append(_skipped_result(check.name))
            continue
        result = check.run(context)
        results.append(result)
        if result.status == "fail":
            fail_reached = True
    return results


def overall_passed(results: Iterable[ReadinessResult]) -> bool:
    """``readiness.overall_passed`` per ``contracts/demo-report-schema.md``.

    True iff every check that ran returned 'pass'. 'skipped' does not block
    true. Any 'fail' makes it False.
    """
    saw_pass = False
    for r in results:
        if r.status == "fail":
            return False
        if r.status == "pass":
            saw_pass = True
    return saw_pass


def first_failing_check_name(results: Iterable[ReadinessResult]) -> str | None:
    """Return the closed-vocabulary name of the first failing check, or None."""
    for r in results:
        if r.status == "fail":
            return r.name  # type: ignore[return-value]
    return None


__all__ = [
    "run_pre_pipeline",
    "run_post_pipeline",
    "overall_passed",
    "first_failing_check_name",
    "READINESS_CHECK_ORDER",
]
