"""US3 Acceptance Scenarios 1-2 + 6: ollama@gpu vs ollama@cpu artifact
contracts are identical; only the lane URL changes.

Spec User Story 3; SC-004; FR-014.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "tests" / "stage1_vendor_identity"


def _ollama_reachable(url: str) -> bool:
    import httpx
    try:
        r = httpx.get(f"{url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture
def opt_in_extract_lanes():
    from ledgerlinc_ocr.pipeline import stages as stages_mod
    stages_mod.register_ollama_gpu()
    stages_mod.register_ollama_cpu()
    try:
        yield
    finally:
        stages_mod.reset_live_registry()


@pytest.mark.skipif(
    not (
        _ollama_reachable(os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        and _ollama_reachable(os.environ.get("OLLAMA_CPU_BASE_URL", "http://localhost:11435"))
    ),
    reason="both Ollama GPU + CPU lanes must be reachable",
)
def test_extract_only_slice_gpu_then_cpu_same_artifact_contract(
    tmp_path: Path, opt_in_extract_lanes
):
    """SC-004: changing extract lane changes only metadata, not contract."""
    from ledgerlinc_ocr.pipeline.cli import main

    src = CORPUS_ROOT / "inv_001_easy" / "source.pdf"
    if not src.exists():
        pytest.skip(f"missing corpus PDF: {src}")

    # Stage two folders (one per lane).
    folder_gpu = tmp_path / "inv_001_easy_gpu"
    folder_cpu = tmp_path / "inv_001_easy_cpu"
    for folder in (folder_gpu, folder_cpu):
        folder.mkdir()
        shutil.copy(src, folder / "source.pdf")

    # Run preprocess + extract under each lane.
    for folder, lane in [(folder_gpu, "gpu"), (folder_cpu, "cpu")]:
        code = main([
            "run",
            "--document-folder", str(folder),
            "--start-at", "preprocess",
            "--stop-after", "extract",
            "--preprocess-profile", "stub",
            "--extract-profile", f"ollama@{lane}",
            "--overwrite",
        ])
        assert code == 0, f"lane {lane} failed"

    import json
    gpu_extract = json.loads(
        (folder_gpu / "edge_extraction_output.json").read_text()
    )
    cpu_extract = json.loads(
        (folder_cpu / "edge_extraction_output.json").read_text()
    )
    # FR-014: filenames + schemas identical.
    # Both artifacts must have the same top-level key set.
    assert set(gpu_extract.keys()) == set(cpu_extract.keys())
