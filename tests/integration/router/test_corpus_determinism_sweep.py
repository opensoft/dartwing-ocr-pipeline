"""T061: Sweep determinism over the stage-1 corpus.

If ``tests/stage1_vendor_identity/inv_*/edge_extraction_output.json``
fixtures are populated (owned by 005/006), run the router twice over
each folder and assert byte-identity except for ``processed_at``. When
the corpus is empty, skip with a pointer at the owning specs.

Per SC-004 / FR-021 the router is deterministic across reruns on the
same input; this is the corpus-wide proof.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


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
    # Run once in a copy, capture artifact; run again in a second copy, diff.
    def _run_once(label: str) -> dict:
        staged = tmp_path / label
        shutil.copytree(corpus_folder, staged)
        # Remove any pre-existing routing_decision.json so we exercise write.
        rd = staged / "routing_decision.json"
        if rd.exists():
            rd.unlink()
        result = subprocess.run(
            [sys.executable, "-m", "ledgerlinc_ocr.router", "route",
             str(staged)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"router failed on {corpus_folder.name}: {result.stderr}"
        )
        return json.loads((staged / "routing_decision.json").read_text())

    a = _run_once("a")
    b = _run_once("b")
    a.pop("processed_at", None)
    b.pop("processed_at", None)
    assert a == b, f"non-determinism on {corpus_folder.name}"
