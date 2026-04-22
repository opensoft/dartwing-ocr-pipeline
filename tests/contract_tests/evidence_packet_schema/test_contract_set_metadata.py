"""T017: v1.1.0 contract_set.json registers evidence_packet as a plain artifact."""
from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACT_SET = (
    _REPO_ROOT
    / "contracts"
    / "stage1_vendor_identity"
    / "v1.1.0"
    / "contract_set.json"
)


def test_contract_set_version_is_1_1_0() -> None:
    data = json.loads(_CONTRACT_SET.read_text(encoding="utf-8"))
    assert data["contract_set_version"] == "1.1.0"


def test_evidence_packet_registered_as_artifact() -> None:
    data = json.loads(_CONTRACT_SET.read_text(encoding="utf-8"))
    assert "evidence_packet" in data["artifact_names"]
    assert data["artifact_schemas"]["evidence_packet"] == "evidence_packet.schema.json"


def test_evidence_packet_not_pipeline_or_policy_versioned() -> None:
    data = json.loads(_CONTRACT_SET.read_text(encoding="utf-8"))
    assert "evidence_packet" not in data["pipeline_versioned_artifacts"]
    assert "evidence_packet" not in data["policy_versioned_artifacts"]
