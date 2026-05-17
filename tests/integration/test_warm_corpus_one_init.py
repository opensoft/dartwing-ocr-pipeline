"""Warm-corpus PPStructureV3 construction-count + first-doc-only test (T019).

GPU-marked. On the workstation, this drives the warm-corpus driver
over two known-good documents and asserts:

- SC-001 / CF7 corpus: PPStructureV3 constructor was invoked exactly
  once across both documents.
- SC-002 / FR-015: doc 0's `phase_timings` carries the GPU one-time
  phases (`paddle_import`, `gpu_bind_probe`, `engine_init`); doc 1's
  `phase_timings` does NOT carry any of those three.
- Both per-doc entries carry the per-doc phases (`rasterization`,
  `artifact_write`, `total`) and a non-empty `per_page_inference`
  array.

The GPU-less unit-level proof of CF5 (engine adoption) lives in
`tests/unit/test_preflight_engine_persistence.py`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


GPU_FIRST_DOC_PHASES = {"paddle_import", "gpu_bind_probe", "engine_init"}
PER_DOC_PHASES = {"rasterization", "artifact_write", "total"}


@pytest.mark.gpu
def test_t019_warm_corpus_constructs_engine_once_across_two_docs(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "tests" / "stage1_vendor_identity"

    # Need at least two known-good documents.
    doc_dirs = sorted(p for p in src_root.iterdir() if p.is_dir() and p.name.startswith("inv_"))
    if len(doc_dirs) < 2:
        pytest.skip("need at least two corpus documents for warm-corpus test")
    doc_a, doc_b = doc_dirs[0], doc_dirs[1]
    src_a = doc_a / "source.pdf"
    src_b = doc_b / "source.pdf"
    if not (src_a.exists() and src_b.exists()):
        pytest.skip("missing source.pdf in one of the candidate documents")

    work_root = tmp_path / "corpus"
    work_root.mkdir()
    work_a = work_root / doc_a.name
    work_b = work_root / doc_b.name
    work_a.mkdir()
    work_b.mkdir()
    (work_a / "source.pdf").write_bytes(src_a.read_bytes())
    (work_b / "source.pdf").write_bytes(src_b.read_bytes())

    docs_file = tmp_path / "docs.txt"
    docs_file.write_text(f"{work_a}\n{work_b}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-m", "dartwing_ocr.pipeline",
            "--documents-file", str(docs_file),
            "--preprocess-profile", "ppstructurev3@gpu",
            "--start-at", "preprocess",
            "--stop-after", "preprocess",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        timeout=900,
    )
    assert result.returncode == 0, (
        f"warm corpus run failed (exit={result.returncode})\n"
        f"stderr:\n{result.stderr}\n"
        f"stdout:\n{result.stdout}"
    )

    # Locate the run_summary line.
    summary = None
    for ln in result.stdout.strip().splitlines():
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("kind") == "run_summary":
            summary = obj
    assert summary is not None, "run_summary line not found in stdout"

    assert summary["schema_version"] == "0.1.4"  # feature 017: 0.1.3 → 0.1.4 (additive top-level fields)
    assert summary["documents_total"] == 2
    assert summary["documents_succeeded"] == 2
    assert summary["preprocess_lane"] == "gpu0"
    assert len(summary["per_document"]) == 2

    doc0, doc1 = summary["per_document"][0], summary["per_document"][1]
    assert doc0["status"] == "success"
    assert doc1["status"] == "success"

    # First doc carries GPU one-time phases (FR-015 / SC-002)
    pt0 = doc0.get("phase_timings", {})
    assert GPU_FIRST_DOC_PHASES <= set(pt0.keys()), (
        f"FR-015: doc 0 must carry all GPU one-time phases; missing "
        f"{GPU_FIRST_DOC_PHASES - set(pt0.keys())}"
    )
    assert PER_DOC_PHASES <= set(pt0.keys())

    # Second doc does NOT carry GPU one-time phases
    pt1 = doc1.get("phase_timings", {})
    leaked = GPU_FIRST_DOC_PHASES & set(pt1.keys())
    assert not leaked, (
        f"FR-015 / SC-002: doc 1 must NOT carry GPU one-time phases; got {leaked}"
    )
    assert PER_DOC_PHASES <= set(pt1.keys())

    # Both docs have non-empty per_page_inference on GPU lane
    for doc, label in ((doc0, "doc0"), (doc1, "doc1")):
        per_page = doc.get("per_page_inference")
        assert per_page is not None and len(per_page) >= 1, (
            f"{label}: per_page_inference must be present and non-empty on GPU lane"
        )
