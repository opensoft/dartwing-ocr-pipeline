"""T091 / SC-009 — reconcile() is byte-deterministic across calls with the same inputs.

Two calls with identical (packet, parsed, config, now, pipeline_version, repair_trail)
must produce byte-identical outputs under `json.dumps(..., sort_keys=True)`. A second
case varies only `now` and `pipeline_version` and asserts exactly those two fields
differ while everything else stays byte-equal.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from dartwing_ocr.extract.config import load_voter_config
from dartwing_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"


def _load_inputs():
    packet = json.loads((_US1_FIXTURE / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((_US1_FIXTURE / "voter_response_clean.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US1_FIXTURE / "voter_config.yaml"),
        base_dir=Path.cwd(),
    )
    return packet, parsed, config


def test_reconcile_is_byte_deterministic() -> None:
    packet, parsed, config = _load_inputs()
    now = datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC)
    pipeline_version = "0.0.0-test+fixture"

    a = reconcile(
        packet=copy.deepcopy(packet),
        parsed=copy.deepcopy(parsed),
        config=config,
        now=now,
        pipeline_version=pipeline_version,
        repair_trail=[],
    )
    b = reconcile(
        packet=copy.deepcopy(packet),
        parsed=copy.deepcopy(parsed),
        config=config,
        now=now,
        pipeline_version=pipeline_version,
        repair_trail=[],
    )

    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), (
        "reconcile() produced divergent outputs for identical inputs"
    )


def test_reconcile_only_time_and_version_vary() -> None:
    packet, parsed, config = _load_inputs()

    now1 = datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC)
    now2 = datetime(2026, 4, 22, 13, 30, 0, tzinfo=UTC)
    pv1 = "0.0.0-test+alpha"
    pv2 = "0.0.0-test+beta"

    a = reconcile(
        packet=copy.deepcopy(packet),
        parsed=copy.deepcopy(parsed),
        config=config,
        now=now1,
        pipeline_version=pv1,
        repair_trail=[],
    )
    b = reconcile(
        packet=copy.deepcopy(packet),
        parsed=copy.deepcopy(parsed),
        config=config,
        now=now2,
        pipeline_version=pv2,
        repair_trail=[],
    )

    assert a["processed_at"] != b["processed_at"]
    assert a["pipeline_version"] != b["pipeline_version"]

    # Normalize the two time-dependent fields, then require byte-equality everywhere else.
    a_norm = copy.deepcopy(a)
    b_norm = copy.deepcopy(b)
    for out in (a_norm, b_norm):
        out["processed_at"] = "<NOW>"
        out["pipeline_version"] = "<PV>"
    assert json.dumps(a_norm, sort_keys=True) == json.dumps(b_norm, sort_keys=True), (
        "reconcile() varied fields other than processed_at and pipeline_version"
    )
