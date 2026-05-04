"""Execution slice (--start-at / --stop-after), prerequisite validation,
and overwrite scoping.

Spec FR-004 / FR-009 / FR-010 / FR-011. Research R-004 / R-005 / R-006.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from ledgerlinc_ocr.pipeline.profiles import STAGES, Stage
from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.loader import load_contract_set
from ledgerlinc_ocr.validator.report import ArtifactName

ARTIFACT_FILENAME_BY_STAGE: dict[Stage, str] = {
    "preprocess": "preprocess_output.json",
    "extract": "edge_extraction_output.json",
    "routing": "routing_decision.json",
    "final_payload": "final_structured_payload.json",
}

_FILENAME_TO_ARTIFACT_NAME: dict[str, ArtifactName] = {
    "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
    "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision.json": ArtifactName.ROUTING_DECISION,
    "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
}


class SliceError(ValueError):
    """Raised when --start-at / --stop-after parsing or validation fails."""


@dataclass(frozen=True)
class ExecutionSlice:
    start_at: Stage
    stop_after: Stage

    @property
    def start_index(self) -> int:
        return STAGES.index(self.start_at)

    @property
    def stop_index(self) -> int:
        return STAGES.index(self.stop_after)

    @property
    def stages_in_slice(self) -> tuple[Stage, ...]:
        return STAGES[self.start_index : self.stop_index + 1]

    @property
    def prerequisite_stages(self) -> tuple[Stage, ...]:
        return STAGES[: self.start_index]

    @property
    def output_artifacts(self) -> tuple[str, ...]:
        return tuple(
            ARTIFACT_FILENAME_BY_STAGE[s] for s in self.stages_in_slice
        )

    @property
    def prerequisite_artifacts(self) -> tuple[str, ...]:
        return tuple(
            ARTIFACT_FILENAME_BY_STAGE[s] for s in self.prerequisite_stages
        )

    @property
    def untouched_artifacts(self) -> tuple[str, ...]:
        return tuple(
            ARTIFACT_FILENAME_BY_STAGE[s]
            for s in STAGES[self.stop_index + 1 :]
        )


def parse_slice(
    *, start_at: str | None, stop_after: str | None
) -> ExecutionSlice:
    """Parse and validate slice bounds. Defaults: full pipeline."""
    start = start_at if start_at is not None else "preprocess"
    stop = stop_after if stop_after is not None else "final_payload"
    if start not in STAGES:
        raise SliceError(
            f"--start-at={start!r}: must be one of {list(STAGES)}"
        )
    if stop not in STAGES:
        raise SliceError(
            f"--stop-after={stop!r}: must be one of {list(STAGES)}"
        )
    if STAGES.index(start) > STAGES.index(stop):  # type: ignore[arg-type]
        raise SliceError(
            f"--start-at={start!r} must not be later than "
            f"--stop-after={stop!r}"
        )
    return ExecutionSlice(start_at=start, stop_after=stop)  # type: ignore[arg-type]


@dataclass(frozen=True)
class PrerequisiteCheckResult:
    ok: bool
    missing_artifact: str | None = None
    invalid_artifact: str | None = None
    invalid_reason: str | None = None


def check_prerequisites(
    *,
    folder: Path,
    slice_: ExecutionSlice,
    contract_set_version: str,
) -> PrerequisiteCheckResult:
    """For each prerequisite stage, require the artifact to exist and validate.

    R-005: missing -> INPUT_NOT_FOUND, schema-invalid -> SCHEMA_VALIDATION_FAILURE.
    The CLI maps these results onto the existing exit codes.
    """
    if slice_.start_at == "preprocess":
        return PrerequisiteCheckResult(ok=True)
    contract_set = load_contract_set(contract_set_version)
    for filename in slice_.prerequisite_artifacts:
        path = folder / filename
        if not path.exists():
            return PrerequisiteCheckResult(
                ok=False, missing_artifact=filename
            )
        outcome = validate_artifact(
            path,
            _FILENAME_TO_ARTIFACT_NAME[filename],
            contract_set=contract_set,
        )
        if not outcome.passed:
            first = outcome.violations[0] if outcome.violations else None
            field = first.field_path if first else "$"
            reason = first.reason if first else "schema validation failed"
            return PrerequisiteCheckResult(
                ok=False,
                invalid_artifact=filename,
                invalid_reason=f"{field}: {reason}",
            )
    return PrerequisiteCheckResult(ok=True)


def existing_outputs_in_slice(
    folder: Path, slice_: ExecutionSlice
) -> list[str]:
    """R-006: only artifacts the slice will write count as outputs-in-use."""
    return [
        filename
        for filename in slice_.output_artifacts
        if (folder / filename).exists()
    ]


__all__ = [
    "ARTIFACT_FILENAME_BY_STAGE",
    "ExecutionSlice",
    "PrerequisiteCheckResult",
    "SliceError",
    "check_prerequisites",
    "existing_outputs_in_slice",
    "parse_slice",
]
