from __future__ import annotations

import json
from pathlib import Path


_CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2] / "contracts" / "stage1_vendor_identity" / "v1.2.0"
)


def test_changed_v1_2_schemas_advertise_v1_2_ids():
    for schema_name in ("preprocess_output", "evidence_packet"):
        schema = json.loads(
            (_CONTRACT_ROOT / f"{schema_name}.schema.json").read_text(encoding="utf-8")
        )
        assert (
            schema["$id"]
            == f"https://ledgerlinc.local/contracts/stage1_vendor_identity/v1.2.0/{schema_name}.schema.json"
        )
