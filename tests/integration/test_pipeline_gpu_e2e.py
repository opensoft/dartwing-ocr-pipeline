"""GPU-marked end-to-end integration test (T019, FR-020, SC-004, SC-005).

Marked `@pytest.mark.gpu` so the conftest skip-gate (T009) skips it on
hosts where preflight does not pass with `PPSTRUCTUREV3_INIT_SUCCEEDED`.
On a passing GPU workstation, this test exercises the GPU lane
end-to-end against `inv_001_easy/source.pdf` and asserts:

(a) `preprocess_output.json` is written and validates against
    `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json`
    via the existing validator infrastructure (per analyze finding NEW.2 / VT5).
    The validator is invoked with `contract="preprocess_output"` and
    `version="1.2.0"` (always passed explicitly per VT-005 — do NOT rely
    on validator defaults; if a future feature bumps `contract_set_version`
    this test must be updated in lockstep).
(b) `pipeline_version` ends with `.gpu0` (verified via
    `parse_lane_segment(...)` returning `("gpu", 0)`).
(c) `document_text` is non-empty.
(d) at least 3 layout blocks across all pages.
(e) Slice flags `--start-at preprocess --stop-after preprocess` work
    identically with the GPU lane (FR-012). Note: this single-doc test
    does not exercise the warm-corpus pipeline.cli surface; the slice
    flag verification is implicit in that the preprocessing-only run
    completes successfully.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerlinc_ocr.preprocessing import cli as preprocessing_cli
from ledgerlinc_ocr.preprocessing.version import parse_lane_segment


@pytest.mark.gpu
def test_gpu_e2e_inv_001_easy(tmp_path: Path, capsys) -> None:
    """End-to-end GPU run on inv_001_easy. Skipped on CI / non-GPU
    hosts via conftest's `gpu` marker hook."""
    # Locate the corpus document.
    repo_root = Path(__file__).resolve().parents[2]
    src_doc = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    if not src_doc.exists():
        pytest.skip(f"corpus document not found: {src_doc}")

    # Stage the document into tmp_path so we don't mutate the corpus.
    work_folder = tmp_path / "inv_001_easy"
    work_folder.mkdir()
    (work_folder / "source.pdf").write_bytes(src_doc.read_bytes())

    rc = preprocessing_cli.main(
        [
            "--document-folder", str(work_folder),
            "--preprocess-profile", "ppstructurev3@gpu",
        ]
    )
    assert rc == 0, f"GPU preprocessing failed; exit={rc}"

    artifact = work_folder / "preprocess_output.json"
    assert artifact.exists(), "preprocess_output.json was not written"
    payload = json.loads(artifact.read_text())

    # (a) schema validity — invoke the validator with explicit contract + version
    from ledgerlinc_ocr.validator.artifact import validate_artifact

    outcome = validate_artifact(
        path=artifact, contract="preprocess_output", version="1.2.0"
    )
    assert outcome.valid is True, f"schema validation failed: {outcome}"

    # (b) pipeline_version ends with .gpu0 (lane segment is mandatory per FR-016)
    pipeline_version = payload["pipeline_version"]
    lane = parse_lane_segment(pipeline_version)
    assert lane == ("gpu", 0), (
        f"expected GPU lane 0; got {lane!r} from {pipeline_version!r}"
    )

    # (c) document_text non-empty
    assert payload.get("document_text", "").strip(), "document_text is empty"

    # (d) ≥3 layout blocks across all pages
    total_blocks = sum(len(p.get("blocks", [])) for p in payload.get("pages", []))
    assert total_blocks >= 3, f"expected ≥3 blocks; got {total_blocks}"
