"""Single-doc CLI run_summary emission test (T014 / FR-014 / R-015.6).

Asserts that on a successful single-document GPU run, the preprocessing
CLI emits exactly one `kind: "run_summary"` JSON line on stdout with
`documents_total: 1` and the new structured `phase_timings` +
`per_page_inference` blocks per FR-014 + the 2026-05-07 clarification.

GPU-marked: skipped on hosts without a working `ppstructurev3@gpu` lane.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


GPU_FIRST_DOC_PHASES = {"paddle_import", "gpu_bind_probe", "engine_init"}
PER_DOC_PHASES = {"rasterization", "artifact_write", "total"}
ALL_PHASE_KEYS = GPU_FIRST_DOC_PHASES | PER_DOC_PHASES | {"warmup"}


@pytest.mark.gpu
def test_t014_single_doc_emits_run_summary_with_phase_timings(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src_doc = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    if not src_doc.exists():
        pytest.skip(f"corpus document not found: {src_doc}")

    work_folder = tmp_path / "inv_001_easy"
    work_folder.mkdir()
    (work_folder / "source.pdf").write_bytes(src_doc.read_bytes())

    # Drive via subprocess so we observe the exact stdout the operator sees.
    result = subprocess.run(
        [
            sys.executable, "-m", "ledgerlinc_ocr.preprocessing",
            "--document-folder", str(work_folder),
            "--preprocess-profile", "ppstructurev3@gpu",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        timeout=600,
    )
    assert result.returncode == 0, (
        f"single-doc GPU run failed (exit={result.returncode})\n"
        f"stderr:\n{result.stderr}\n"
        f"stdout:\n{result.stdout}"
    )

    # Parse every JSONL stdout line; locate the run_summary line.
    lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    parsed_lines = []
    for ln in lines:
        try:
            parsed_lines.append(json.loads(ln))
        except json.JSONDecodeError:
            pytest.fail(f"non-JSON stdout line: {ln!r}")

    summary_lines = [p for p in parsed_lines if isinstance(p, dict) and p.get("kind") == "run_summary"]
    assert len(summary_lines) == 1, (
        f"expected exactly one kind: 'run_summary' line; found {len(summary_lines)}"
    )
    summary = summary_lines[0]

    # Top-level shape (FR-014)
    assert summary["schema_version"] == "0.1.2"
    assert summary["documents_total"] == 1
    assert summary["documents_succeeded"] == 1
    assert summary["preprocess_lane"] == "gpu0"
    assert len(summary["per_document"]) == 1

    entry = summary["per_document"][0]
    assert entry["status"] == "success"

    # Phase timings (FR-013 + Clarification Q3 shape)
    assert "phase_timings" in entry, "FR-014: per-doc record must carry phase_timings"
    phase_timings = entry["phase_timings"]

    # Subset of canonical FR-013 vocabulary; warmup absent (Q2)
    assert set(phase_timings.keys()) <= ALL_PHASE_KEYS
    assert "warmup" not in phase_timings, "Q2: feature 015 does not perform warmup"

    # First-doc rule: GPU one-time phases present
    assert GPU_FIRST_DOC_PHASES <= set(phase_timings.keys()), (
        f"FR-015: first-doc must include all GPU one-time phases; "
        f"missing {GPU_FIRST_DOC_PHASES - set(phase_timings.keys())}"
    )
    # Steady-state phases present
    assert PER_DOC_PHASES <= set(phase_timings.keys()), (
        f"FR-013: per-doc phases must all be present; "
        f"missing {PER_DOC_PHASES - set(phase_timings.keys())}"
    )

    # Each phase record has shape {"seconds": <float>}
    for name, value in phase_timings.items():
        assert set(value.keys()) == {"seconds"}, (
            f"PT1: phase {name!r} must have only 'seconds' key, got {set(value.keys())}"
        )
        assert isinstance(value["seconds"], (int, float))
        assert value["seconds"] >= 0

    # per_page_inference (Q3 shape)
    assert "per_page_inference" in entry, "FR-014: per-doc record must carry per_page_inference on GPU lane"
    per_page = entry["per_page_inference"]
    assert isinstance(per_page, list) and len(per_page) >= 1
    pages = [p["page"] for p in per_page]
    assert pages[0] == 1, "PT3: per_page_inference is 1-based"
    assert pages == sorted(pages), "PT3: per_page_inference is strictly ascending"
    for p in per_page:
        assert set(p.keys()) == {"page", "seconds"}
        assert isinstance(p["page"], int) and p["page"] >= 1
        assert isinstance(p["seconds"], (int, float)) and p["seconds"] >= 0

    # Legacy flat keys preserved (back-compat per FR-014 + R-015.4)
    stages = entry.get("stages", {})
    preprocess_stage = stages.get("preprocess", {})
    assert "total_seconds" in preprocess_stage, "back-compat: legacy total_seconds must persist in 0.1.2"
    assert "gpu_init_seconds" in preprocess_stage, "back-compat: gpu_init_seconds must persist on first GPU doc"
    assert "gpu_inference_seconds" in preprocess_stage, "back-compat: gpu_inference_seconds must persist on GPU"
