"""US1 AC#1 — artifact written to the per-document folder and validates against the frozen schema."""

from __future__ import annotations

from pathlib import Path

from dartwing_ocr.validator import ArtifactName, validate_artifact


def test_ac1_artifact_written_and_validates(us1_happy_folder: Path, run_extractor, load_output) -> None:
    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    artifact_path = us1_happy_folder / "edge_extraction_output.json"
    assert artifact_path.is_file(), "extractor did not write edge_extraction_output.json"

    outcome = validate_artifact(artifact_path, ArtifactName.EDGE_EXTRACTION_OUTPUT)
    assert outcome.passed, f"schema validation errors: {outcome.violations}"

    payload = load_output(us1_happy_folder)
    assert payload["contract_set_version"] == "1.0.0"
