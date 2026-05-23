"""Tests for the v1.3.0 contract-set integrity (R-022.5 / FR-031 / SC-008 / F9 resolution).

Validates that:

* ``contract_set_version`` is exactly ``"1.3.0"``.
* Every v1.2.0 schema file is present at v1.3.0 and byte-identical to its
  v1.2.0 source EXCEPT the four amended schemas
  (``evaluation_document.schema.json``, ``evaluation_run_summary.schema.json``,
  ``folder.schema.json``, ``contract_set.json``). Note the four amended
  schemas land in later phases (US3 — T048, T049 + Phase 2 T006 for
  contract_set itself); T014 only enforces the byte-identity of CARRIED
  schemas at Phase 2 landing time.
* The new ``semantic_table_truth.schema.json`` is listed in
  ``contract_set.json`` and loads as a valid JSON Schema Draft 2020-12.
* ``expected.schema.json`` is byte-identical v1.2.0 → v1.3.0 (FR-006 /
  MI-23 / F9 resolution — guards against silent shape drift in the
  vendor-identity truth contract).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_2_DIR = REPO_ROOT / "contracts" / "stage1_vendor_identity" / "v1.2.0"
V1_3_DIR = REPO_ROOT / "contracts" / "stage1_vendor_identity" / "v1.3.0"

# Schemas amended at v1.3.0 — these are EXPECTED to differ from v1.2.0 by
# the time US3 (T048, T049) and Phase 2 (T006) land. T014 does not assert
# byte-identity on these; it only confirms they exist at v1.3.0.
AMENDED_SCHEMAS = frozenset({
    "evaluation_document.schema.json",
    "evaluation_run_summary.schema.json",
    "folder.schema.json",
    "contract_set.json",
})

# Schemas carried byte-identical from v1.2.0 to v1.3.0 (R-022.5).
CARRIED_SCHEMAS = frozenset({
    "preprocess_output.schema.json",
    "edge_extraction_output.schema.json",
    "routing_decision.schema.json",
    "final_structured_payload.schema.json",
    "evidence_packet.schema.json",
    "expected.schema.json",
    "README.md",
})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v1_3_contract_set_version_is_1_3_0() -> None:
    """T006: contract_set_version pinned to '1.3.0' at v1.3.0."""
    content = json.loads((V1_3_DIR / "contract_set.json").read_text(encoding="utf-8"))
    assert content["contract_set_version"] == "1.3.0"


def test_v1_3_lists_semantic_table_truth_schema() -> None:
    """T006: semantic_table_truth is listed in artifact_names AND artifact_schemas."""
    content = json.loads((V1_3_DIR / "contract_set.json").read_text(encoding="utf-8"))
    assert "semantic_table_truth" in content["artifact_names"]
    assert content["artifact_schemas"]["semantic_table_truth"] == (
        "semantic_table_truth.schema.json"
    )


def test_semantic_table_truth_schema_file_exists() -> None:
    """T005: the new schema file is present at v1.3.0."""
    assert (V1_3_DIR / "semantic_table_truth.schema.json").is_file()


def test_semantic_table_truth_schema_is_draft_2020_12() -> None:
    """T005: the new schema declares Draft 2020-12."""
    content = json.loads(
        (V1_3_DIR / "semantic_table_truth.schema.json").read_text(encoding="utf-8")
    )
    assert content["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert content["$id"].endswith(
        "/v1.3.0/semantic_table_truth.schema.json"
    )
    assert content["type"] == "object"
    assert set(content["required"]) == {"document_id", "rows"}
    assert content["additionalProperties"] is False


def test_semantic_table_truth_schema_loads_as_valid_jsonschema() -> None:
    """T005: the schema is loadable by the jsonschema Draft 2020-12 validator."""
    from jsonschema import Draft202012Validator

    content = json.loads(
        (V1_3_DIR / "semantic_table_truth.schema.json").read_text(encoding="utf-8")
    )
    # Validate the schema itself against the Draft 2020-12 metaschema.
    Draft202012Validator.check_schema(content)


def test_semantic_table_truth_safety_pattern_landed() -> None:
    """Q-SEC-2/B: document_id AND row_id carry the safety pattern + maxLength:64."""
    content = json.loads(
        (V1_3_DIR / "semantic_table_truth.schema.json").read_text(encoding="utf-8")
    )
    safety_pattern = "^[A-Za-z0-9_-]{1,64}$"

    doc_id = content["properties"]["document_id"]
    assert doc_id["pattern"] == safety_pattern
    assert doc_id["maxLength"] == 64
    assert doc_id["minLength"] == 1

    row_id = content["$defs"]["row"]["properties"]["row_id"]
    assert row_id["pattern"] == safety_pattern
    assert row_id["maxLength"] == 64
    assert row_id["minLength"] == 1


@pytest.mark.parametrize("schema_name", sorted(CARRIED_SCHEMAS))
def test_carried_schemas_byte_identical(schema_name: str) -> None:
    """R-022.5: every carried-unchanged schema is byte-identical v1.2.0 → v1.3.0."""
    src = V1_2_DIR / schema_name
    dst = V1_3_DIR / schema_name
    assert src.exists(), f"v1.2.0 source missing: {src}"
    assert dst.exists(), f"v1.3.0 target missing: {dst}"
    assert _sha256(src) == _sha256(dst), (
        f"{schema_name} differs between v1.2.0 and v1.3.0; expected byte-identical carry"
    )


def test_expected_schema_byte_identical_f9_resolution() -> None:
    """F9 resolution / FR-006 / MI-23: expected.schema.json is byte-identical v1.2.0 → v1.3.0.

    Guards against silent shape drift in the vendor-identity truth
    contract; expected.json semantics MUST NOT change with the v1.3.0
    bump.
    """
    src = V1_2_DIR / "expected.schema.json"
    dst = V1_3_DIR / "expected.schema.json"
    assert _sha256(src) == _sha256(dst)


def test_amended_schemas_present_at_v1_3() -> None:
    """All four amended schemas exist at v1.3.0 (content checks happen in US3 tests T043/T044/T017)."""
    for schema_name in AMENDED_SCHEMAS:
        assert (V1_3_DIR / schema_name).is_file(), (
            f"v1.3.0 amended schema missing: {schema_name}"
        )
