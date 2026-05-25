"""Closed exit-code table for the GPU MVP demo CLI (FR-021).

The demo CLI emits exactly one of these six codes; the mapping from
``(runtime_outcome, failure_kind)`` pairs to exit codes is documented in
``contracts/cli-contract.md`` §"Exit codes".
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Closed 0–5 exit-code table per FR-021."""

    SUCCESS = 0
    READINESS_FAILED = 1
    INVALID_INPUT = 2
    PIPELINE_RUNTIME_TIMEOUT = 3
    PIPELINE_RUNTIME_ERROR = 4
    ARTIFACT_SCHEMA_VALIDATION_FAILED = 5
