"""T026: company-name provenance triad for missing_name folders."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from ledgerlinc_ocr.pipeline.cli import main
from ledgerlinc_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES, Runner
from ledgerlinc_ocr.pipeline.stages import (
    default_extraction,
    default_final_payload,
    default_preprocess,
    default_routing,
)
from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.report import ArtifactName


def _inferred_extraction(
    invocation: Any, artifacts_so_far: dict[str, Any]
) -> dict[str, Any]:
    payload = default_extraction(invocation, artifacts_so_far)
    payload["vendor_candidate"]["company_name"] = {
        "value": "Best Guess LLC",
        "present": False,
        "inferred": True,
        "confidence": 0.4,
        "evidence": [],
    }
    return payload


def test_provenance_triad_enforced(
    tmp_document_folder: Callable[..., Path],
):
    folder = tmp_document_folder(999, "missing_name")
    runner = Runner(extraction=_inferred_extraction)
    code = main(
        ["run", "--document-folder", str(folder)], runner=runner
    )
    assert code == 0

    routing = json.loads((folder / "routing_decision.json").read_text())
    final = json.loads(
        (folder / "final_structured_payload.json").read_text()
    )
    extraction = json.loads(
        (folder / "edge_extraction_output.json").read_text()
    )

    cn = extraction["vendor_candidate"]["company_name"]
    assert cn["present"] is False
    assert cn["inferred"] is True

    assert routing["decision"] == "edge_review_required"
    assert routing["review_status"]["manual_review_required"] is True
    assert routing["review_status"]["review_reason"] == "company_name_inferred"
    assert (
        final["review_status"]["review_reason"] == "company_name_inferred"
    )

    mapping = {
        "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
        "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
        "routing_decision.json": ArtifactName.ROUTING_DECISION,
        "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
    }
    for name in RESERVED_ARTIFACT_NAMES:
        outcome = validate_artifact(folder / name, mapping[name], version="1.0.0")
        assert outcome.passed, [v.reason for v in outcome.violations]
