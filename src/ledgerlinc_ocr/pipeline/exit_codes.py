"""Exit code vocabulary and structured failure record.

Contract: specs/002-cli-contract/contracts/exit-codes.md
Contract: specs/002-cli-contract/contracts/stderr-failure-record.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Literal

Stage = Literal[
    "arguments",
    "input_validation",
    "preprocess",
    "extraction",
    "routing",
    "final_payload",
    "schema_validation",
]

STAGES: tuple[Stage, ...] = (
    "arguments",
    "input_validation",
    "preprocess",
    "extraction",
    "routing",
    "final_payload",
    "schema_validation",
)


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE_ERROR = 10
    INPUT_NOT_FOUND = 11
    INVALID_PDF = 12
    OUTPUT_IN_USE = 13
    OUTPUT_PATH_NOT_USABLE = 14
    # Feature 016 (T011 / FR-007 / SC-011 / contracts/cli-contract.md §4):
    # the explicit GPU warmup pass raised a MIOpen/COMGR/Paddle error.
    # Slots immediately after feature 014's preflight 10–14 codes per
    # research R-016.6. Caught at the runner / corpus_run boundary; surfaced
    # as `error: warmup failed: <cause-class>: <message>` on stderr with
    # no run_summary line emitted (SC-011).
    WARMUP_FAILED = 15
    # Feature 017 (T003 / R-017.9 / R-017.12 / contracts/cli-contract.md §4):
    # an unknown `module_set_id` or `det_rec_variant_id` value was selected
    # (typo / unknown preset). Caught at the CLI parse boundary BEFORE any
    # Paddle import; surfaced as `error: unknown <preset_axis>: <value!r> —
    # valid values are: <…>` on stderr with no run_summary line emitted.
    # See `preprocessing/presets.py::resolve_module_set` /
    # `resolve_det_rec_variant` (US1/US2) and the catch sites in
    # `preprocessing/cli.py` and `pipeline/cli.py`.
    UNKNOWN_PRESET = 16
    PROCESSING_FAILURE = 20
    SCHEMA_VALIDATION_FAILURE = 30


@dataclass
class StructuredFailureRecord:
    exit_code: int
    exit_code_name: str
    stage: str
    message: str
    artifacts_written: list[str] = field(default_factory=list)

    def as_json_line(self) -> str:
        payload = {
            "exit_code": self.exit_code,
            "exit_code_name": self.exit_code_name,
            "stage": self.stage,
            "message": self.message,
            "artifacts_written": list(self.artifacts_written),
        }
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def for_code(
        cls,
        code: ExitCode,
        *,
        stage: str,
        message: str,
        artifacts_written: list[str] | None = None,
    ) -> "StructuredFailureRecord":
        return cls(
            exit_code=int(code),
            exit_code_name=code.name,
            stage=stage,
            message=message,
            artifacts_written=list(artifacts_written or []),
        )
