"""T021 / US1 AC#6 + SC-004: byte-identical reruns except ``processed_at``.

The earlier version of this test reused a single ``tmp_path`` for both runs,
so the second run overwrote the first and we only ever compared one set of
bytes against itself. That's overwrite idempotence, not determinism.

This version stages the same fixture into two independent folders, runs the
CLI once per folder, and compares the raw on-disk bytes after stripping
``processed_at``. That's the byte-identity guarantee FR-021 / SC-004
actually pin.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path


PROCESSED_AT_LINE = re.compile(
    rb'^ {2}"processed_at": "[0-9T:Z-]+",\n',
    re.MULTILINE,
)


def _strip_processed_at_line(raw: bytes) -> bytes:
    """Delete the single ``processed_at`` line so the rest can be byte-compared."""
    stripped, n = PROCESSED_AT_LINE.subn(b"", raw, count=1)
    assert n == 1, f"expected exactly one processed_at line, got {n}"
    return stripped


def test_two_independent_runs_are_byte_identical_except_processed_at(
    tmp_path: Path, stage_fixture, run_cli
):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    folder_a = stage_fixture(tmp_path / "a", "clean_explicit_name_full_identity.json")
    folder_b = stage_fixture(tmp_path / "b", "clean_explicit_name_full_identity.json")

    run_cli(folder_a)
    # Give the clock room to advance so processed_at CAN differ between runs —
    # if it doesn't differ we'd be testing the wrong thing.
    time.sleep(1.1)
    run_cli(folder_b)

    raw_a = (folder_a / "routing_decision.json").read_bytes()
    raw_b = (folder_b / "routing_decision.json").read_bytes()

    # Sanity: the processed_at values really did differ, otherwise this test
    # isn't actually proving the "byte-identical EXCEPT processed_at" claim.
    ts_a = json.loads(raw_a)["processed_at"]
    ts_b = json.loads(raw_b)["processed_at"]
    assert ts_a != ts_b, (
        "processed_at did not differ between runs; test cannot distinguish "
        "byte-identity-except-timestamp from full byte-identity"
    )

    stripped_a = _strip_processed_at_line(raw_a)
    stripped_b = _strip_processed_at_line(raw_b)
    assert stripped_a == stripped_b, (
        "routing_decision.json bytes differ across independent runs after "
        "stripping processed_at; this is a determinism regression"
    )
