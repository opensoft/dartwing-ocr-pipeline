"""Pipeline orchestration skeleton.

The runner executes stages 3–6 (preprocess, extraction, routing, final_payload)
in order, writing one artifact per stage into the destination folder. After all
four are written, stage 7 validates them against the installed v1.0.0 contract
set via the existing validator module.

Stages are pluggable callables so tests and downstream features can inject
real implementations without changing the CLI surface.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ledgerlinc_ocr.pipeline.exit_codes import ExitCode
from ledgerlinc_ocr.pipeline.stages import (
    default_extraction,
    default_final_payload,
    default_preprocess,
    default_routing,
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


@dataclass
class CLIInvocation:
    input_pdf: Path
    destination_folder: Path
    document_id: str
    overwrite: bool
    pipeline_version: str
    policy_version: str
    contract_set_version: str
    ollama_url: str
    log_level: str
    timeout: int


StageCallable = Callable[[CLIInvocation, dict[str, Any]], dict[str, Any]]


@dataclass
class RunResult:
    exit_code: ExitCode
    artifacts_written: list[Path] = field(default_factory=list)
    stage: str = "schema_validation"
    message: str = ""
    routing_decision: dict[str, Any] | None = None


_STAGE_SEQUENCE: tuple[tuple[str, str], ...] = (
    ("preprocess_output.json", "preprocess"),
    ("edge_extraction_output.json", "extraction"),
    ("routing_decision.json", "routing"),
    ("final_structured_payload.json", "final_payload"),
)


class Runner:
    def __init__(
        self,
        *,
        preprocess: StageCallable | None = None,
        extraction: StageCallable | None = None,
        routing: StageCallable | None = None,
        final_payload: StageCallable | None = None,
    ) -> None:
        self._stages: dict[str, StageCallable] = {
            "preprocess_output.json": preprocess or default_preprocess,
            "edge_extraction_output.json": extraction or default_extraction,
            "routing_decision.json": routing or default_routing,
            "final_structured_payload.json": final_payload or default_final_payload,
        }

    def run(self, invocation: CLIInvocation) -> RunResult:
        artifacts_written: list[Path] = []
        produced: dict[str, Any] = {}

        for filename, stage_name in _STAGE_SEQUENCE:
            dest = invocation.destination_folder / filename
            try:
                payload = self._stages[filename](invocation, produced)
            except Exception as exc:  # noqa: BLE001 — contract: convert to failure
                return RunResult(
                    exit_code=ExitCode.PROCESSING_FAILURE,
                    artifacts_written=artifacts_written,
                    stage=stage_name,
                    message=str(exc) or type(exc).__name__,
                )
            try:
                dest.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as exc:
                return RunResult(
                    exit_code=ExitCode.PROCESSING_FAILURE,
                    artifacts_written=artifacts_written,
                    stage=stage_name,
                    message=f"failed to write {filename}: {exc}",
                )
            produced[filename] = payload
            artifacts_written.append(dest.resolve())

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
                )

        routing_path = invocation.destination_folder / "routing_decision.json"
        routing_payload = produced["routing_decision.json"]
        return RunResult(
            exit_code=ExitCode.SUCCESS,
            artifacts_written=artifacts_written,
            stage="schema_validation",
            message="",
            routing_decision=routing_payload,
        )
