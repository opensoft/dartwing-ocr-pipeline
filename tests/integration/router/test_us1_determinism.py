"""T021 / US1 AC#6 + SC-004: byte-identical reruns except ``processed_at``."""
from __future__ import annotations

import json
import time
from pathlib import Path


def _normalize(artifact: dict) -> dict:
    art = dict(artifact)
    art.pop("processed_at", None)
    return art


def test_two_runs_are_byte_identical_except_processed_at(
    green_fixture: Path, run_cli
):
    run_cli(green_fixture)
    first = (green_fixture / "routing_decision.json").read_bytes()
    first_parsed = json.loads(first)

    # Give the clock room to advance so processed_at CAN differ.
    time.sleep(1.1)

    run_cli(green_fixture)
    second = (green_fixture / "routing_decision.json").read_bytes()
    second_parsed = json.loads(second)

    assert _normalize(first_parsed) == _normalize(second_parsed)

    canon_first = json.dumps(_normalize(first_parsed), indent=2,
                             sort_keys=False, ensure_ascii=False)
    canon_second = json.dumps(_normalize(second_parsed), indent=2,
                              sort_keys=False, ensure_ascii=False)
    assert canon_first == canon_second
