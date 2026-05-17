"""T046: harness corpus loop over 20 generated folders + validator folder-check."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from dartwing_ocr.pipeline.cli import main
from dartwing_ocr.pipeline.runner import RESERVED_ARTIFACT_NAMES
from dartwing_ocr.validator.artifact import validate_artifact
from dartwing_ocr.validator.report import ArtifactName

_ARTIFACT_MAP = {
    "preprocess_output.json": ArtifactName.PREPROCESS_OUTPUT,
    "edge_extraction_output.json": ArtifactName.EDGE_EXTRACTION_OUTPUT,
    "routing_decision.json": ArtifactName.ROUTING_DECISION,
    "final_structured_payload.json": ArtifactName.FINAL_STRUCTURED_PAYLOAD,
}


def test_corpus_loop_produces_four_artifacts_per_folder(
    tmp_corpus_root: Callable[[int], Path],
):
    root = tmp_corpus_root(20)
    folders = sorted(p for p in root.iterdir() if p.is_dir())
    assert len(folders) == 20

    for folder in folders:
        code = main(
            ["run", "--document-folder", str(folder), "--overwrite"]
        )
        assert code == 0, f"failed at {folder.name}"

    for folder in folders:
        names = {p.name for p in folder.iterdir() if p.is_file()}
        assert set(RESERVED_ARTIFACT_NAMES) <= names
        assert "source.pdf" in names

        for artifact_name, contract in _ARTIFACT_MAP.items():
            outcome = validate_artifact(
                folder / artifact_name, contract, version="1.0.0"
            )
            assert outcome.passed, (
                f"{folder.name}/{artifact_name}: "
                f"{[v.reason for v in outcome.violations]}"
            )
