"""T016: v1.1.0 folder contract reserves evidence_packet.json (optional)."""
from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FOLDER_SCHEMA = (
    _REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.1.0"
    / "folder.schema.json"
)


def test_folder_schema_reserves_evidence_packet_filename() -> None:
    data = json.loads(_FOLDER_SCHEMA.read_text(encoding="utf-8"))
    assert "evidence_packet.json" in data["reserved_generated_filenames"]


def test_folder_schema_retains_prior_reserved_names() -> None:
    data = json.loads(_FOLDER_SCHEMA.read_text(encoding="utf-8"))
    for name in [
        "preprocess_output.json",
        "edge_extraction_output.json",
        "routing_decision.json",
        "final_structured_payload.json",
        "evaluation_document.json",
    ]:
        assert name in data["reserved_generated_filenames"]
