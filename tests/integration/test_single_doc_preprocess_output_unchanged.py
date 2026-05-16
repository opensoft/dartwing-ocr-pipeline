"""Single-doc preprocess_output.json shape regression test (T015 / FR-010
/ CH1 / SC-003).

Asserts that on a feature-015 GPU run on `inv_001_easy/source.pdf`:

(a) `preprocess_output.json` validates against the active stage 1 contract
    set (1.2.0) — invokes the existing validator with explicit version.
(b) `pipeline_version` ends in `.gpu0` (lane segment).
(c) `document_text` (assembled from text-bearing blocks) is non-empty.
(d) The count of layout blocks across all pages is ≥ 3.
(e) Top-level keys equal exactly the v1.2.0 contract set — no
    `phase_timings`, no `per_page_inference`, no other timing additions.

GPU-marked: skipped on hosts without a working `ppstructurev3@gpu` lane.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


EXPECTED_TOP_LEVEL_KEYS = {
    "schema_version",
    "contract_set_version",
    "pipeline_version",
    "document_id",
    "source_file",
    "pages",
    "tables",
    "quality",
    "ingestion_sources",
    "warnings",
}


@pytest.mark.gpu
def test_t015_preprocess_output_unchanged_with_sc003_subcriteria(tmp_path: Path) -> None:
    from dartwing_ocr.preprocessing import cli as preprocessing_cli
    from dartwing_ocr.preprocessing.version import parse_lane_segment
    from dartwing_ocr.validator.artifact import validate_artifact

    repo_root = Path(__file__).resolve().parents[2]
    src_doc = repo_root / "tests" / "stage1_vendor_identity" / "inv_001_easy" / "source.pdf"
    if not src_doc.exists():
        pytest.skip(f"corpus document not found: {src_doc}")

    work_folder = tmp_path / "inv_001_easy"
    work_folder.mkdir()
    (work_folder / "source.pdf").write_bytes(src_doc.read_bytes())

    rc = preprocessing_cli.main([
        "--document-folder", str(work_folder),
        "--preprocess-profile", "ppstructurev3@gpu",
    ])
    assert rc == 0, f"GPU preprocessing failed; exit={rc}"

    artifact = work_folder / "preprocess_output.json"
    assert artifact.exists(), "preprocess_output.json was not written"
    payload = json.loads(artifact.read_text())

    # SC-003 (a): validates against the active 1.2.0 contract set.
    outcome = validate_artifact(path=artifact, contract="preprocess_output", version="1.2.0")
    assert outcome.valid is True, f"SC-003(a): contract validation failed: {outcome}"

    # SC-003 (b): pipeline_version ends in .gpu0
    pipeline_version = payload["pipeline_version"]
    lane = parse_lane_segment(pipeline_version)
    assert lane == ("gpu", 0), (
        f"SC-003(b): expected GPU lane 0; got {lane!r} from {pipeline_version!r}"
    )

    # SC-003 (c): document_text is non-empty.
    # The assembled document_text is computed by the assembler stage in some
    # call paths; for preprocess_output.json we proxy on the union of
    # text-bearing block text per the existing convention.
    text_pieces: list[str] = []
    for page in payload.get("pages", []):
        for block in page.get("blocks", []):
            t = block.get("text") or ""
            if t.strip():
                text_pieces.append(t)
    assert text_pieces, "SC-003(c): no non-empty text-bearing blocks emitted"

    # SC-003 (d): ≥ 3 layout blocks across all pages.
    total_blocks = sum(len(page.get("blocks", [])) for page in payload.get("pages", []))
    assert total_blocks >= 3, (
        f"SC-003(d): expected ≥3 layout blocks across pages; got {total_blocks}"
    )

    # FR-010 / CH1: top-level keys unchanged from v1.2.0 contract set.
    actual_keys = set(payload.keys())
    assert actual_keys == EXPECTED_TOP_LEVEL_KEYS, (
        f"FR-010 / CH1: preprocess_output.json top-level keys drifted.\n"
        f"unexpected: {actual_keys - EXPECTED_TOP_LEVEL_KEYS}\n"
        f"missing: {EXPECTED_TOP_LEVEL_KEYS - actual_keys}"
    )

    # Explicit negative assertions: the new run_summary keys MUST NOT have
    # leaked into preprocess_output.json (FR-010 + Q1 channel rule).
    assert "phase_timings" not in payload
    assert "per_page_inference" not in payload
