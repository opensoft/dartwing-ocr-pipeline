"""T081 — atomic-write + pre-write validation coverage for artifact.py."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dartwing_ocr.extract.artifact import assemble_and_write
from dartwing_ocr.extract.config import load_voter_config
from dartwing_ocr.extract.errors import ArtifactAssemblyError, FolderWriteError
from dartwing_ocr.extract.reconcile import reconcile

_REPO_ROOT = Path(__file__).resolve().parents[3]
_US1 = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"


def _build_valid_artifact() -> dict:
    packet = json.loads((_US1 / "preprocess_output.json").read_text(encoding="utf-8"))
    parsed = json.loads((_US1 / "voter_response_clean.json").read_text(encoding="utf-8"))
    config, _, _ = load_voter_config(
        name_or_path=str(_US1 / "voter_config.yaml"), base_dir=Path.cwd()
    )
    return reconcile(
        packet=packet,
        parsed=parsed,
        config=config,
        now=datetime(2026, 4, 21, 12, 0, 0, tzinfo=UTC),
        pipeline_version="0.0.0-test+fixture",
        repair_trail=[],
    )


def test_successful_write_produces_only_final_artifact(tmp_path: Path) -> None:
    artifact = _build_valid_artifact()
    final = assemble_and_write(artifact, tmp_path)

    assert final == tmp_path / "edge_extraction_output.json"
    assert final.is_file()

    # Only one file under the target folder — no stray temp sidecars.
    assert sorted(p.name for p in tmp_path.iterdir()) == ["edge_extraction_output.json"]

    # Content is the serialized artifact.
    on_disk = json.loads(final.read_text(encoding="utf-8"))
    assert on_disk["document_id"] == artifact["document_id"]


def test_invalid_artifact_rejected_before_any_final_write(tmp_path: Path) -> None:
    """Corrupt the artifact so it fails schema — assert the final file never appears
    and no leftover `.tmp-<pid>` sibling survives."""

    artifact = _build_valid_artifact()
    broken = copy.deepcopy(artifact)
    broken.pop("document_id")  # required by schema

    with pytest.raises(ArtifactAssemblyError):
        assemble_and_write(broken, tmp_path)

    assert not (tmp_path / "edge_extraction_output.json").exists()
    # No tmp sidecars survived the validator rejection.
    for p in tmp_path.iterdir():
        assert not p.name.startswith(".edge_extraction_output."), (
            f"temp sidecar leaked after validation failure: {p}"
        )


def test_non_directory_target_raises_folder_write_error(tmp_path: Path) -> None:
    bogus = tmp_path / "not-a-real-dir"
    artifact = _build_valid_artifact()
    with pytest.raises(FolderWriteError):
        assemble_and_write(artifact, bogus)
    assert not bogus.exists()


def test_overwrite_of_existing_artifact_is_atomic(tmp_path: Path) -> None:
    """A second successful write overwrites the first — no stale sidecars remain."""

    artifact = _build_valid_artifact()
    assemble_and_write(artifact, tmp_path)
    first = (tmp_path / "edge_extraction_output.json").read_text(encoding="utf-8")

    modified = copy.deepcopy(artifact)
    modified["pipeline_version"] = "0.0.0-test+round2"
    assemble_and_write(modified, tmp_path)

    second = (tmp_path / "edge_extraction_output.json").read_text(encoding="utf-8")
    assert first != second
    assert json.loads(second)["pipeline_version"] == "0.0.0-test+round2"

    # One file, no `.tmp-<pid>` siblings.
    assert [p.name for p in tmp_path.iterdir()] == ["edge_extraction_output.json"]
