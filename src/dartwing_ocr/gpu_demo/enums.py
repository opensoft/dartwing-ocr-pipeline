"""Closed Literal enums for the DemoRunReport shape.

Mirrors ``data-model.md`` §4 and ``contracts/demo-report-schema.md``.
Every closed vocabulary is exhaustive — no implicit "other" / "unknown".
Adding a new value is a minor schema_version bump per the report-shape
forward-compat policy.
"""

from __future__ import annotations

from typing import Literal


RuntimeOutcome = Literal[
    "success",
    "failed_at_preprocess",
    "failed_at_extraction",
    "failed_at_routing",
    "failed_at_final_payload",
    "timeout",
]

StalledPhase = Literal["preprocess", "extraction", "routing", "final_payload"]

QualityStatus = Literal["pass", "weak", "review_required"]

QualityStatusSource = Literal["gate", "evaluator"]

FailureKind = Literal[
    "readiness-failed",
    "invalid-input",
    "pipeline-runtime-timeout",
    "pipeline-runtime-error",
    "artifact-schema-validation-failed",
    "cpu-fallback-detected",
    "post-run-interrogation-unreachable",
]

ReadinessCheckName = Literal[
    "interpreter/venv",
    "paddle-rocm-preflight",
    "ollama-reachability",
    "ollama-version",
    "ollama-model-gpu-placement",
    "ollama-context-length",
    "artifact-schema-validation",
    "pipeline-runtime-timeout",
]

ReadinessCheckStatus = Literal["pass", "fail", "skipped"]

ProbeResult = Literal["consistent", "fell_back", "unreachable", "skipped"]


READINESS_CHECK_ORDER: tuple[ReadinessCheckName, ...] = (
    "interpreter/venv",
    "paddle-rocm-preflight",
    "ollama-reachability",
    "ollama-version",
    "ollama-model-gpu-placement",
    "ollama-context-length",
    "artifact-schema-validation",
    "pipeline-runtime-timeout",
)

DEMO_REPORT_KIND = "demo_run_report"
DEMO_REPORT_SCHEMA_VERSION = "0.1.0"
BOUNDED_TIMEOUT_SECONDS = 600
READINESS_BUDGET_SECONDS = 10
MIN_OLLAMA_VERSION = "0.4.0"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_CONTEXT_LENGTH = 2048
DEFAULT_PRESET = "header-first-v1"
SUPPORTED_PRESETS: tuple[str, ...] = ("header-first-v1", "full-ocr")
DEFAULT_DOCUMENT_FOLDER = "tests/stage1_vendor_identity/inv_001_easy"

CANONICAL_ARTIFACT_BASENAMES: tuple[str, str, str, str] = (
    "preprocess_output.json",
    "edge_extraction_output.json",
    "routing_decision.json",
    "final_structured_payload.json",
)
