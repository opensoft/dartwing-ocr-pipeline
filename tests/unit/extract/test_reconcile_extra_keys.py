"""T096 / analyze C1 — Edge Case L125: extra keys in the model response are
silently dropped (no schema violation, no warning). The contract shape is
authoritative; the model's inventive extensions never reach disk.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from ledgerlinc_ocr.extract.config import load_voter_config
from ledgerlinc_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"

_NOW = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
_PV = "0.0.0-test+extra-keys"


def _load_inputs():
    packet = json.loads((_US1 / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((_US1 / "voter_response_clean.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US1 / "voter_config.yaml"), base_dir=Path.cwd()
    )
    return packet, parsed, config


def test_extra_model_keys_dropped_silently() -> None:
    """Extra keys at top level, inside sub-blocks, and inside individual fields
    must not survive reconciliation. No `warnings` entry is required — the
    schema contract is what downstream consumers rely on."""

    packet, parsed, config = _load_inputs()
    parsed = copy.deepcopy(parsed)

    parsed["extra_top_level"] = "sneaky"
    parsed["vendor_candidate"]["foo"] = "bar"
    parsed["vendor_candidate"]["company_name"]["extra_subkey"] = 42

    out = reconcile(
        packet=packet,
        parsed=parsed,
        config=config,
        now=_NOW,
        pipeline_version=_PV,
        repair_trail=[],
    )

    assert "extra_top_level" not in out
    assert "foo" not in out["vendor_candidate"]
    assert "extra_subkey" not in out["vendor_candidate"]["company_name"]

    joined = "\n".join(out["warnings"])
    assert "extra_top_level" not in joined
    assert "foo" not in joined
    assert "extra_subkey" not in joined

    assert out["status"] == "success"
