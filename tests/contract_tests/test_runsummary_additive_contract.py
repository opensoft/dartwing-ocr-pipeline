"""RunSummary additive contract test (T026 / R-014.6 / Plan §Contract Test Coverage point 4).

Simulates a feature-011 0.1.0-shape parser and runs it against a sample
0.1.1 `RunSummary.to_json_dict()` output. Asserts:
- the parser does NOT raise on the new fields;
- all pre-feature fields are preserved with their original semantics;
- new keys (`preprocess_lane`, `gpu_init_seconds`, `gpu_inference_seconds`,
  `gpu_lane_forced_abort`) are silently ignored by the 0.1.0 parser.
"""
from __future__ import annotations

import json

from ledgerlinc_ocr.pipeline.timing import (
    RunSummary,
    SCHEMA_VERSION,
    build_per_document_failure,
    build_per_document_success,
)


# Pre-feature 0.1.0 key set (drawn from feature 011 timing.py):
_FEATURE_011_TOP_LEVEL_KEYS = {
    "kind",
    "schema_version",
    "stack_preset",
    "resolved_profiles",
    "execution_slice",
    "on_failure",
    "documents_total",
    "documents_succeeded",
    "documents_failed",
    "profile_initialization_seconds",
    "per_document",
}

_FEATURE_011_PER_DOCUMENT_SUCCESS_KEYS = {"document_id", "folder", "status", "stages"}
_FEATURE_011_PER_DOCUMENT_FAILURE_KEYS = {
    "document_id",
    "folder",
    "status",
    "failed_stage",
    "exit_code",
    "message",
}


def _simulate_0_1_0_parser(payload: dict) -> dict:
    """A pre-feature 0.1.0 parser ignores unknown keys and returns
    only the keys it knew about. This mimics what existing feature-011
    consumers do when they encounter post-feature-014 output."""
    parsed = {k: payload[k] for k in _FEATURE_011_TOP_LEVEL_KEYS if k in payload}
    pre_feature_per_doc = []
    for entry in payload.get("per_document", []):
        if entry.get("status") == "success":
            kept = {
                k: entry[k] for k in _FEATURE_011_PER_DOCUMENT_SUCCESS_KEYS if k in entry
            }
        else:
            kept = {
                k: entry[k] for k in _FEATURE_011_PER_DOCUMENT_FAILURE_KEYS if k in entry
            }
        pre_feature_per_doc.append(kept)
    parsed["per_document"] = pre_feature_per_doc
    return parsed


def test_0_1_0_parser_reads_0_1_1_output_without_raising() -> None:
    """Build a sample 0.1.1 RunSummary with all the new additive fields
    and verify a 0.1.0-shape parser still consumes it cleanly."""
    summary = RunSummary(
        stack_preset=None,
        resolved_profiles={"preprocess": "ppstructurev3@gpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=2,
        documents_succeeded=1,
        documents_failed=1,
        profile_initialization_seconds={"preprocess": 8.42},
        per_document=[
            {
                "document_id": "inv_001_easy",
                "folder": "tests/stage1_vendor_identity/inv_001_easy",
                "status": "success",
                "stages": {
                    "preprocess": {
                        "total_seconds": 1.234567,
                        "gpu_init_seconds": 8.42,
                        "gpu_inference_seconds": 1.123,
                    }
                },
            },
            build_per_document_failure(
                document_id="inv_002_medium",
                folder="tests/stage1_vendor_identity/inv_002_medium",
                failed_stage="preprocess",
                exit_code=2,
                message="[ppstructurev3@gpu] document_id=inv_002_medium: ROCm OOM",
                gpu_lane_forced_abort=True,
            ),
        ],
        preprocess_lane="gpu0",
    )
    payload = summary.to_dict()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["preprocess_lane"] == "gpu0"

    # 0.1.0-shape parser succeeds and preserves pre-feature fields.
    parsed = _simulate_0_1_0_parser(payload)
    assert parsed["kind"] == "run_summary"
    assert parsed["schema_version"] == "0.1.1"  # the value, not the schema, is read
    assert parsed["resolved_profiles"] == {"preprocess": "ppstructurev3@gpu"}
    assert parsed["documents_total"] == 2
    assert parsed["documents_succeeded"] == 1
    assert parsed["documents_failed"] == 1

    # New top-level key `preprocess_lane` is silently ignored.
    assert "preprocess_lane" not in parsed

    # Per-document success entry: pre-feature keys preserved.
    success_entry = parsed["per_document"][0]
    assert set(success_entry.keys()) == _FEATURE_011_PER_DOCUMENT_SUCCESS_KEYS
    # Inner `stages.preprocess` map MAY contain new GPU keys; the 0.1.0
    # consumer either ignores them or uses them — both are valid.

    # Per-document failure entry: `gpu_lane_forced_abort` is silently dropped.
    failure_entry = parsed["per_document"][1]
    assert "gpu_lane_forced_abort" not in failure_entry
    assert failure_entry["status"] == "failure"
    assert failure_entry["failed_stage"] == "preprocess"


def test_runsummary_serializes_to_valid_json() -> None:
    """Smoke test: to_json_dict + json.dumps round-trip is stable."""
    summary = RunSummary(
        stack_preset="full-workstation",
        resolved_profiles={"preprocess": "ppstructurev3@cpu"},
        execution_slice={"start_at": "preprocess", "stop_after": "preprocess"},
        on_failure="continue",
        documents_total=0,
        documents_succeeded=0,
        documents_failed=0,
    )
    line = summary.as_json_line()
    assert line.endswith("}\n") is False  # as_json_line returns the JSON string itself, no newline
    parsed = json.loads(line)
    assert parsed["kind"] == "run_summary"
