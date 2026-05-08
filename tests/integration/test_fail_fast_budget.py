"""GPU prereq fail-fast budget regression test (T035 / FF1 / SC-007 / FR-008).

Drives the preprocessing CLI on a host where GPU prerequisites are
missing (or where `HIP_VISIBLE_DEVICES=""` forces `GPU_NOT_EXPOSED`)
and asserts:

- Wall-clock from OS exec to first non-zero exit ≤ 10 s (SC-007).
- Exit code is one of {10, 11, 12, 13, 14} (the FR-001-state-mapped codes).
- No `preprocess_output.json` whose `pipeline_version` ends in `.gpu0`
  was written by this run.
- FR-008 silent-fallback guard: no `preprocess_output.json` whose
  `pipeline_version` ends in `.cpu0` was written either.

CPU-runnable; this test must run on GPU-less hosts (NOT marked `@pytest.mark.gpu`).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_t035_gpu_prereq_failure_within_10s_no_silent_fallback(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_doc = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    if not src_doc.exists():
        pytest.skip(f"corpus document not found: {src_doc}")

    work_folder = tmp_path / "inv_001_easy"
    work_folder.mkdir()
    (work_folder / "source.pdf").write_bytes(src_doc.read_bytes())

    # Force GPU_NOT_EXPOSED via HIP_VISIBLE_DEVICES="" so the test
    # exercises the failure path even on a GPU host.
    env = dict(os.environ)
    env["HIP_VISIBLE_DEVICES"] = ""
    env["CUDA_VISIBLE_DEVICES"] = ""
    # Ensure subprocess uses the worktree source (not the parent repo's
    # editable install) so feature-015 changes are picked up.
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")

    t0 = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable, "-m", "ledgerlinc_ocr.preprocessing",
            "--document-folder", str(work_folder),
            "--preprocess-profile", "ppstructurev3@gpu",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        env=env,
        timeout=30,
    )
    t1 = time.perf_counter()

    elapsed = t1 - t0

    # SC-007: ≤ 10 seconds wall-clock from OS exec to non-zero exit.
    assert elapsed < 10.0, (
        f"FF1 / SC-007: GPU prereq failure exceeded 10 s budget "
        f"(elapsed={elapsed:.3f}s, exit={result.returncode}, "
        f"stderr={result.stderr[:300]!r})"
    )

    # Exit code is one of the FR-001-state-mapped codes (10–14).
    assert result.returncode in {10, 11, 12, 13, 14}, (
        f"FF1: exit code {result.returncode} is not in the FR-001 "
        f"fail-state range (10-14); stderr={result.stderr[:300]!r}"
    )

    # FR-008: no `preprocess_output.json` whose `pipeline_version` ends
    # in `.gpu0` was written by this run, and no silent-fallback `.cpu0`
    # artifact either.
    artifact = work_folder / "preprocess_output.json"
    if artifact.exists():
        payload = json.loads(artifact.read_text())
        pv = payload.get("pipeline_version", "")
        assert not pv.endswith(".gpu0"), (
            f"FR-008: preprocess_output.json with pipeline_version='{pv}' was "
            f"written despite GPU prereq failure"
        )
        assert not pv.endswith(".cpu0"), (
            f"FR-008: silent fallback to CPU is forbidden; pipeline_version='{pv}' "
            f"was written despite explicit --preprocess-profile=ppstructurev3@gpu"
        )
