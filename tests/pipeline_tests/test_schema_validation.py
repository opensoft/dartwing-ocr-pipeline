"""T018: post-hoc v1.0.0 schema validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES, Runner
from ledgerlinc_ocr.pipeline.stages import default_preprocess
from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.report import ArtifactName


def _bad_preprocess(invocation: Any, produced: dict) -> dict:
    # Missing required fields — should fail schema validation.
    return {"not": "valid"}


def test_invalid_artifact_returns_schema_failure(
    tmp_document_folder: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
):
    folder = tmp_document_folder(1, "easy")
    runner = Runner(preprocess=_bad_preprocess)
    code = main(
        ["run", "--document-folder", str(folder), "--overwrite"],
        runner=runner,
    )
    assert code == 30
    rec = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert rec["exit_code_name"] == "SCHEMA_VALIDATION_FAILURE"
    assert rec["stage"] == "schema_validation"
    assert "preprocess_output.json" in rec["message"]


def test_clean_run_all_artifacts_validate(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(1, "easy")
    code = main(["run", "--document-folder", str(folder)])
    assert code == 0

    mapping = {
        "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
        "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
        "routing_decision.json": ArtifactName.ROUTING_DECISION,
        "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
    }
    for name in RESERVED_ARTIFACT_NAMES:
        outcome = validate_artifact(folder / name, mapping[name], version="1.0.0")
        assert outcome.passed, (
            f"{name} failed validation: {[v.reason for v in outcome.violations]}"
        )
