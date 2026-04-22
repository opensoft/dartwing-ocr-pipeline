"""T037 — schema-level guardrail for US1 happy-path extractor output.

Runs the stub-backed extractor end-to-end against the US1 fixture, then
re-validates the resulting `edge_extraction_output.json` against the
frozen `edge_extraction_output.schema.json` in contract set v1.0.0 and
asserts the `company_name.present XOR inferred` invariant.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ledgerlinc_ocr.extract.cli import main as extract_main
from ledgerlinc_ocr.validator import ArtifactName, validate_artifact

_REPO_ROOT = Path(__file__).resolve().parents[2]
_US1_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "extract" / "us1_happy"


def test_us1_happy_fixture_shape(tmp_path: Path) -> None:
    dest = tmp_path / "us1_happy"
    shutil.copytree(_US1_FIXTURE, dest)

    rc = extract_main(
        [
            "--folder",
            str(dest),
            "--voter",
            "stub",
            "--voter-config",
            str(dest / "voter_config.yaml"),
        ]
    )
    assert rc == 0, "stub extractor did not exit 0 on the US1 happy-path fixture"

    artifact_path = dest / "edge_extraction_output.json"
    assert artifact_path.is_file()

    outcome = validate_artifact(artifact_path, ArtifactName.EDGE_EXTRACTION_OUTPUT)
    assert outcome.passed, f"schema validation errors: {outcome.violations}"

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    cn = payload["vendor_candidate"]["company_name"]
    assert isinstance(cn["present"], bool)
    assert isinstance(cn["inferred"], bool)
    assert cn["present"] != cn["inferred"], (
        f"company_name must satisfy present XOR inferred; "
        f"got present={cn['present']!r}, inferred={cn['inferred']!r}"
    )
