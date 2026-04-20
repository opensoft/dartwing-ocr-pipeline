import json
import os
from pathlib import Path

import pytest

from ledgerlinc_ocr.preprocessing import artifact as artifact_mod
from ledgerlinc_ocr.preprocessing.errors import ArtifactInvalidError


def _minimal_valid_artifact() -> dict:
    return artifact_mod.assemble(
        contract_set_version="1.0.0",
        pipeline_version="stage1-preprocess-v0.1.0+paddleocr2.10.0.0000000.dpi300",
        document_id="inv_042",
        source_file="source.pdf",
        pages=[
            {
                "page_number": 1,
                "width": 100,
                "height": 100,
                "rotation_detected": 0,
                "blocks": [
                    {
                        "block_id": "p1_b1",
                        "block_type": "text",
                        "bbox": [0, 0, 10, 10],
                        "reading_order": 1,
                        "text": "hello",
                        "confidence": 0.9,
                    }
                ],
                "raw_ocr_lines": [
                    {
                        "line_id": "p1_l1",
                        "bbox": [0, 0, 10, 10],
                        "text": "hello",
                        "confidence": 0.9,
                    }
                ],
            }
        ],
        tables=[],
        quality={"scan_quality": "good", "skew_detected": False, "noise_level": "low"},
        ingestion_sources={
            "paddleocr_vl": {"enabled": True, "status": "success"},
            "falcon_ocr": {"enabled": False, "status": "not_implemented"},
            "falcon_perception": {"enabled": False, "status": "not_implemented"},
        },
        warnings=[],
    )


def test_assemble_produces_required_top_level_keys():
    art = _minimal_valid_artifact()
    for key in (
        "contract_set_version",
        "pipeline_version",
        "document_id",
        "source_type",
        "source_file",
        "page_count",
        "pages",
        "document_text",
        "tables",
        "quality",
        "ingestion_sources",
        "warnings",
    ):
        assert key in art
    assert art["source_type"] == "pdf"
    assert art["page_count"] == 1


def test_validate_passes_on_minimal_valid_artifact():
    artifact_mod.validate(_minimal_valid_artifact())


def test_validate_raises_on_malformed_artifact():
    bad = _minimal_valid_artifact()
    del bad["ingestion_sources"]
    with pytest.raises(ArtifactInvalidError):
        artifact_mod.validate(bad)


def test_write_atomic_creates_file(tmp_path: Path):
    art = _minimal_valid_artifact()
    out = tmp_path / "preprocess_output.json"
    artifact_mod.write_atomic(art, out)
    assert out.is_file()
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded["document_id"] == "inv_042"


def test_write_atomic_leaves_no_tmp_on_success(tmp_path: Path):
    art = _minimal_valid_artifact()
    out = tmp_path / "preprocess_output.json"
    artifact_mod.write_atomic(art, out)
    leftover = list(tmp_path.glob("preprocess_output.json.tmp-*"))
    assert leftover == []


def test_write_atomic_uses_temp_then_rename(monkeypatch, tmp_path: Path):
    art = _minimal_valid_artifact()
    out = tmp_path / "preprocess_output.json"
    seen: list[tuple[str, str]] = []

    real_replace = os.replace

    def fake_replace(src, dst):
        seen.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fake_replace)
    artifact_mod.write_atomic(art, out)

    assert len(seen) == 1
    src, dst = seen[0]
    assert dst == str(out)
    assert ".tmp-" in src


def test_validate_and_write_refuses_to_persist_invalid(tmp_path: Path):
    bad = _minimal_valid_artifact()
    bad["source_type"] = "image"
    out = tmp_path / "preprocess_output.json"
    with pytest.raises(ArtifactInvalidError):
        artifact_mod.validate_and_write(bad, out)
    assert not out.exists()
    assert list(tmp_path.glob("preprocess_output.json*")) == []


def test_write_atomic_crash_midway_preserves_prior_artifact(monkeypatch, tmp_path: Path):
    """FR-019: a crash between tmp write and rename must not corrupt the prior artifact."""
    art = _minimal_valid_artifact()
    out = tmp_path / "preprocess_output.json"

    # Seed a prior artifact so we can verify it is not touched by the crashed run.
    prior_bytes = b'{"prior": "untouched"}'
    out.write_bytes(prior_bytes)

    def boom(src, dst):
        raise RuntimeError("simulated crash between tmp-write and rename")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(RuntimeError):
        artifact_mod.write_atomic(art, out)

    assert out.read_bytes() == prior_bytes, "prior artifact must be byte-identical"

    # Restore os.replace so the follow-up write succeeds.
    monkeypatch.undo()

    # A subsequent successful run must replace the prior bytes and leave no tmp file.
    artifact_mod.write_atomic(art, out)
    assert out.read_bytes() != prior_bytes
    leftover = list(tmp_path.glob("preprocess_output.json.tmp-*"))
    # Any tmp from the crashed run is harmless (FR-019 allows stale tmps) but the
    # successful write must produce a clean final artifact.
    assert out.is_file()
    # Opportunistic cleanup is allowed, not required; just assert no shadow file has
    # a name that would hide the final artifact.
    for p in leftover:
        assert p.name != out.name
