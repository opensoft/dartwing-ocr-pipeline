"""T017 (US1): contract-level tests for the v1.3.0 folder contract.

The folder.schema.json file is consumed by the validator as a JSON config
(not as a JSON Schema for another JSON file). At v1.3.0 the only delta is
that ``semantic_table_truth.json`` is listed as an OPTIONAL per-document
file alongside the unchanged mandatory ``source.pdf`` and ``expected.json``.

Covers the four T017 cases (a)-(d).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_2_FOLDER = (
    REPO_ROOT / "contracts" / "stage1_vendor_identity" / "v1.2.0" / "folder.schema.json"
)
V1_3_FOLDER = (
    REPO_ROOT / "contracts" / "stage1_vendor_identity" / "v1.3.0" / "folder.schema.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# (a) Folder contract still accepts the absence of a sidecar — mandatory
#     artifacts unchanged from v1.2.0.
def test_a_v1_3_folder_keeps_v1_2_required_files() -> None:
    v1_2 = _load(V1_2_FOLDER)
    v1_3 = _load(V1_3_FOLDER)

    assert v1_2["required_files"]["unconditional"] == v1_3["required_files"]["unconditional"]
    assert sorted(v1_3["required_files"]["unconditional"]) == ["expected.json", "source.pdf"]


# (b) `semantic_table_truth.json` is RESERVED / LISTED at v1.3.0.
def test_b_v1_3_folder_lists_semantic_table_truth_optional() -> None:
    v1_3 = _load(V1_3_FOLDER)
    reserved = set(v1_3["reserved_generated_filenames"])
    optional = set(v1_3.get("optional_files") or [])
    # The sidecar appears on either the reserved or the optional list — never
    # on the unconditional-mandatory list (that would break FR-005).
    assert "semantic_table_truth.json" in (reserved | optional)
    assert "semantic_table_truth.json" not in v1_3["required_files"]["unconditional"]


# (c) Mandatory artifacts are unchanged from v1.2.0.
def test_c_v1_3_mandatory_unchanged_from_v1_2() -> None:
    v1_2 = _load(V1_2_FOLDER)
    v1_3 = _load(V1_3_FOLDER)

    # `required_files` block — both unconditional and notes_md_by_difficulty.
    assert v1_2["required_files"] == v1_3["required_files"]
    # difficulty_values + folder_name_pattern unchanged.
    assert v1_2["folder_name_pattern"] == v1_3["folder_name_pattern"]
    assert v1_2["difficulty_values"] == v1_3["difficulty_values"]


# (d) v1.3.0 folder contract carries v1.3.0 identification ($id / $schema /
#     comment string referencing v1.3.0 or otherwise present such that the
#     validator can route it).
def test_d_v1_3_folder_carries_v1_3_identifier() -> None:
    v1_3 = _load(V1_3_FOLDER)
    serialized = json.dumps(v1_3)
    # Either an explicit $id ending with v1.3.0 OR a stable comment/identifier
    # — the validator loads it via the contract-set loader, so the test just
    # confirms a v1.3.0 marker is present somewhere.
    assert "1.3.0" in serialized or v1_3.get("$id", "").endswith(
        "folder_contract_schema_v1.3.0"
    )
