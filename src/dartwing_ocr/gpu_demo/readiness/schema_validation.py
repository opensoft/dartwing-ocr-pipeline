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


def _validate_artifact(path: Path) -> Optional[str]:
    """Validate one artifact; return None on pass or the error message on fail."""
    if not path.exists():
        return f"file does not exist: {path}"
    try:
        # Lazy import — keeps the readiness package light when tests stub
        # the orchestrator entirely.
        from dartwing_ocr.validator import artifact as artifact_validator

        artifact_validator.validate_path(path)  # type: ignore[attr-defined]
    except ImportError as exc:
        return f"validator import failed: {exc}"
    except Exception as exc:  # noqa: BLE001 — validator exposes its own taxonomy
        return f"{type(exc).__name__}: {exc}"
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
