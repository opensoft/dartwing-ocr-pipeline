"""T012 [US1] — assembled output validates against the frozen v1.0.0 schema."""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlinc_ocr.assembler import Invocation, run
from ledgerlinc_ocr.validator.artifact import validate_artifact
from ledgerlinc_ocr.validator.report import ArtifactName

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "assembler"


def test_happy_grounded_validates_against_v1_0_0_schema(tmp_path: Path):
    src = FIXTURE_ROOT / "happy_grounded"
    # Copy to a fresh tmp folder so the test is hermetic.
    dst = tmp_path / "happy_grounded"
    dst.mkdir()
    for name in ("edge_extraction_output.json", "routing_decision.json"):
        (dst / name).write_bytes((src / name).read_bytes())

    out_path = run(Invocation(document_folder=dst))
    assert out_path.exists()

    outcome = validate_artifact(out_path, ArtifactName.FINAL_STRUCTURED_PAYLOAD)
    assert outcome.passed, (
        "final_structured_payload.json failed schema validation: "
        f"{[v.reason for v in outcome.violations]}"
    )

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["contract_set_version"] == "1.0.0"
