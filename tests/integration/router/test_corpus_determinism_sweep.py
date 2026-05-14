"""T061: Sweep determinism over the stage-1 corpus.

If ``tests/stage1_vendor_identity/inv_*/edge_extraction_output.json``
fixtures are populated (owned by 005/006), run the router twice over
each folder and assert byte-identity except for ``processed_at``. When
the corpus is empty, skip with a pointer at the owning specs.

Per SC-004 / FR-021 the router is deterministic across reruns on the
same input; this is the corpus-wide proof. Compares the raw on-disk
bytes (minus the single ``processed_at`` line) rather than parsed
``dict``s so key-order drift — itself an FR-002 regression — also
trips this sweep instead of being silently normalized away.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"

PROCESSED_AT_LINE = re.compile(
    rb'^  "processed_at": "[0-9T:Z\-]+",\n',
    re.MULTILINE,
)


def _strip_processed_at_line(raw: bytes) -> bytes:
    stripped, n = PROCESSED_AT_LINE.subn(b"", raw, count=1)
    assert n == 1, f"expected exactly one processed_at line, got {n}"
    return stripped


def _discover_corpus_folders() -> list[Path]:
    if not CORPUS_ROOT.exists():
        return []
    return sorted(
        p.parent
        for p in CORPUS_ROOT.glob("inv_*/edge_extraction_output.json")
    )


CORPUS_FOLDERS = _discover_corpus_folders()


@pytest.mark.skipif(
    not CORPUS_FOLDERS,
    reason=(
        "stage-1 corpus is not populated; see specs/005 (corpus) and "
        "specs/006 (extraction) for the owning features"
    ),
)
@pytest.mark.parametrize("corpus_folder", CORPUS_FOLDERS, ids=lambda p: p.name)
def test_corpus_determinism(tmp_path: Path, corpus_folder: Path):
    def _run_once(label: str) -> bytes:
        staged = tmp_path / label
        shutil.copytree(corpus_folder, staged)
        rd = staged / "routing_decision.json"
        if rd.exists():
            rd.unlink()
        result = subprocess.run(
            [sys.executable, "-m", "dartwing_ocr.router", "route",
             str(staged)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"router failed on {corpus_folder.name}: {result.stderr}"
        )
        return (staged / "routing_decision.json").read_bytes()

    raw_a = _run_once("a")
    # Sleep past the one-second processed_at granularity so the two runs have
    # DIFFERENT timestamps — otherwise byte-identity-except-timestamp would
    # be indistinguishable from full byte-identity and we'd be testing less
    # than FR-021/SC-004 claim.
    time.sleep(1.1)
    raw_b = _run_once("b")

    ts_a = json.loads(raw_a)["processed_at"]
    ts_b = json.loads(raw_b)["processed_at"]
    assert ts_a != ts_b, (
        f"processed_at did not differ on {corpus_folder.name}; test cannot "
        "distinguish byte-identity-except-timestamp from full byte-identity"
    )

    stripped_a = _strip_processed_at_line(raw_a)
    stripped_b = _strip_processed_at_line(raw_b)
    assert stripped_a == stripped_b, (
        f"non-determinism on {corpus_folder.name}: routing_decision.json "
        "bytes differ across independent runs after stripping processed_at"
    )
