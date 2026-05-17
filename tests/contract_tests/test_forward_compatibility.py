"""T079a: SC-008 forward-compat demonstration.

The stage 1 contract set is deliberately shaped so that switching from
single-voter to three-voter ensemble mode in a future version does NOT require
changes to `preprocess_output`, `final_structured_payload`, `expected`, or the
folder layout. Only `edge_extraction_output.vote_metadata.consensus_mode` and
`routing_decision.decision` must add new enum values when ensemble mode is
turned on. This test proves both halves of that claim:

  - Unchanged-shape artifacts validate cleanly under `1.0.0`.
  - Artifacts that carry ensemble-specific values fail under `1.0.0` ONLY at
    the specific enum fields SC-008 permits to evolve.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from dartwing_ocr.validator import ArtifactName, validate_artifact
from dartwing_ocr.validator.report import ViolationCode

_HERE = Path(__file__).resolve().parent
_FWD = _HERE / "fixtures" / "forward_compat"


@pytest.mark.parametrize(
    "stem,contract",
    [
        ("preprocess_output", ArtifactName.PREPROCESS_OUTPUT),
        ("final_structured_payload", ArtifactName.FINAL_STRUCTURED_PAYLOAD),
        ("expected", ArtifactName.EXPECTED),
    ],
)
def test_unchanged_shape_artifacts_still_pass_under_1_0_0(
    stem: str, contract: ArtifactName
) -> None:
    outcome = validate_artifact(_FWD / f"{stem}.json", contract)
    assert outcome.passed, [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]


def test_future_consensus_mode_fails_only_at_the_consensus_mode_field() -> None:
    outcome = validate_artifact(
        _FWD / "edge_extraction_output.json",
        ArtifactName.EDGE_EXTRACTION_OUTPUT,
    )
    assert not outcome.passed
    # Every error must be an enum violation located at consensus_mode — no
    # structural breakage elsewhere.
    assert outcome.violations, "expected at least one violation"
    for v in outcome.violations:
        assert v.violation_code == ViolationCode.SCHEMA_ENUM_VIOLATION, (
            f"unexpected non-enum violation at {v.field_path}: {v.violation_code}"
        )
        assert v.field_path.endswith("consensus_mode"), (
            f"violation at wrong field path: {v.field_path}"
        )


def test_future_decision_value_fails_only_at_the_decision_field() -> None:
    outcome = validate_artifact(
        _FWD / "routing_decision.json",
        ArtifactName.ROUTING_DECISION,
    )
    assert not outcome.passed
    assert outcome.violations
    for v in outcome.violations:
        assert v.violation_code == ViolationCode.SCHEMA_ENUM_VIOLATION, (
            f"unexpected non-enum violation at {v.field_path}: {v.violation_code}"
        )
        assert v.field_path == "/decision", (
            f"violation at wrong field path: {v.field_path}"
        )


def test_folder_layout_shape_unchanged(
    good_fixtures_root: Path,
) -> None:
    """The folder contract at 1.0.0 still accepts the good folder unchanged —
    proving that ensemble-readiness (reserved `votes/` and
    `consensus_output.json`) does not require a folder contract change."""
    from dartwing_ocr.validator import validate_folder
    outcome = validate_folder(good_fixtures_root / "folders" / "inv_001_easy")
    assert outcome.passed
