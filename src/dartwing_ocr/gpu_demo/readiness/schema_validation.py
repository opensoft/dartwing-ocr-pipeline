"""Readiness check 7 — artifact-schema-validation (T031, FR-009).

Runs AFTER the four pipeline phases produce their artifacts. Validates each
of the four canonical artifacts against its v1.3.0 schema using the existing
``dartwing_ocr.validator`` API. On failure, aggregates ALL failing artifacts
into the diagnostic's ``observed`` list per Q5/CHK052 (preserving canonical
artifact order).

This check is invoked by the orchestrator after the pipeline phases complete,
NOT during the pre-pipeline readiness phase. The runner marks it ``skipped``
under ``--check-only`` (FR-018).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dartwing_ocr.gpu_demo.enums import CANONICAL_ARTIFACT_BASENAMES
from dartwing_ocr.gpu_demo.readiness.base import (
    ReadinessContext,
    ReadinessResult,
)
from dartwing_ocr.gpu_demo.report import CheckDiagnostic


_BASENAME_TO_ARTIFACT_NAME: dict[str, str] = {
    "preprocess_output.json": "preprocess_output",
    "edge_extraction_output.json": "edge_extraction_output",
    "routing_decision.json": "routing_decision",
    "final_structured_payload.json": "final_structured_payload",
}


def _validate_artifact(path: Path) -> Optional[str]:
    """Validate one artifact; return None on pass or the error message on fail.

    Calls ``dartwing_ocr.validator.validate_artifact(path, contract=<name>)``
    using the closed basename → ArtifactName mapping. The validator returns a
    ``ValidationOutcome`` whose ``.passed`` boolean drives this check; on
    failure we surface the first violation's code + path for the diagnostic.
    """
    if not path.exists():
        return f"file does not exist: {path}"
    contract = _BASENAME_TO_ARTIFACT_NAME.get(path.name)
    if contract is None:
        return f"no contract mapping for basename: {path.name}"
    try:
        # Lazy import — keeps the readiness package light when tests stub
        # the orchestrator entirely.
        from dartwing_ocr.validator import validate_artifact
    except ImportError as exc:
        return f"validator import failed: {exc}"
    try:
        outcome = validate_artifact(path, contract=contract)
    except Exception as exc:  # noqa: BLE001 — validator exposes its own taxonomy
        return f"{type(exc).__name__}: {exc}"
    if outcome.passed:
        return None
    # R2-1 (round-2 triage): the real Violation model exposes `violation_code`
    # and `reason` (NOT `code`/`message` — those were a fictional API the
    # round-1 B1 fix referenced). Previously this branch raised AttributeError
    # on the first real schema failure, swallowed by the outer Exception
    # catch, surfacing as an opaque stringified attribute error.
    if outcome.violations:
        first = outcome.violations[0]
        return f"{first.violation_code} at {first.field_path or '/'}: {first.reason}"
    # R2-12 (round-2 triage): a failed sub-report (e.g. nested folder
    # validation) populates `outcome.sub_reports` not `outcome.violations`.
    # Surface the first leaf violation found by walking the sub-report tree;
    # without this walk operators would see the misleading "no violations"
    # fallback that originally guarded an impossible state.
    leaf = _first_leaf_violation(outcome)
    if leaf is not None:
        return f"{leaf.violation_code} at {leaf.field_path or '/'}: {leaf.reason}"
    return "schema validation failed via sub-report (no leaf violation surfaced)"


def _first_leaf_violation(outcome):
    """Walk sub_reports recursively and return the first Violation found."""
    for sub in getattr(outcome, "sub_reports", []) or []:
        if sub.violations:
            return sub.violations[0]
        leaf = _first_leaf_violation(sub)
        if leaf is not None:
            return leaf
    return None


@dataclass(frozen=True)
class ArtifactSchemaValidationCheck:
    """Validates the four canonical artifacts post-pipeline."""

    name: str = "artifact-schema-validation"

    def run(self, context: ReadinessContext) -> ReadinessResult:
        start = time.monotonic()
        if context.check_only:
            return ReadinessResult(
                name=self.name,
                status="skipped",
                elapsed_seconds=0.0,
            )
        if context.document_folder is None:
            return ReadinessResult(
                name=self.name,
                status="skipped",
                elapsed_seconds=0.0,
            )

        failures: list[dict[str, str]] = []
        for basename in CANONICAL_ARTIFACT_BASENAMES:
            path = context.document_folder / basename
            err = _validate_artifact(path)
            if err is not None:
                failures.append({"path": str(path), "error": err})

        elapsed = time.monotonic() - start
        if not failures:
            return ReadinessResult(
                name=self.name,
                status="pass",
                elapsed_seconds=elapsed,
            )

        return ReadinessResult(
            name=self.name,
            status="fail",
            elapsed_seconds=elapsed,
            diagnostic=CheckDiagnostic(
                checked="Schema validation of 4 canonical artifacts",
                observed=failures,
                expected="all four artifacts schema-valid against v1.3.0 contract set",
                remediation=(
                    "Inspect the listed artifact(s); a multi-artifact failure "
                    "usually indicates a deeper pipeline regression — start with "
                    "the earliest failure in canonical order."
                ),
            ),
        )
