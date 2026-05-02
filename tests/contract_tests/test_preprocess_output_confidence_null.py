"""T056 — FR-004 / R-013 contract gate: confidence=null is permitted under v1.2.0.

Covers the FR-004 rule that preprocessing persists engine-emitted confidence
verbatim and uses `null` (never `0.0`) when the engine omits a score. The
underlying schema change landed in AMENDMENTS v1.2.0 (2026-04-23, branch
010-pp-structurev3-preprocessing): `preprocess_output.block.confidence` and
`preprocess_output.ocr_line.confidence` both widened from `"number"` to
`["number", "null"]`. Numeric bounds `[0.0, 1.0]` remain in place for non-null
values. This test is the positive contract gate for that amendment.
"""

from __future__ import annotations

import json
from pathlib import Path

from ledgerlinc_ocr.validator import ArtifactName, validate_artifact
from ledgerlinc_ocr.validator.loader import load_contract_set


_HERE = Path(__file__).resolve().parent
_FIXTURE = _HERE / "fixtures" / "preprocess_output" / "confidence_null.json"


def test_fixture_has_null_confidence_on_block_and_line():
    """Sanity-check the fixture's shape before handing it to the validator."""
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert data["contract_set_version"] == "1.2.0"
    null_blocks = [
        b
        for p in data["pages"]
        for b in p["blocks"]
        if b["confidence"] is None
    ]
    null_lines = [
        ln
        for p in data["pages"]
        for ln in p["raw_ocr_lines"]
        if ln["confidence"] is None
    ]
    assert len(null_blocks) >= 1, "fixture must exercise block confidence=null"
    assert len(null_lines) >= 1, "fixture must exercise raw_ocr_line confidence=null"


def test_confidence_null_validates_against_v1_2_0():
    """Positive contract gate: confidence=null must validate under v1.2.0."""
    outcome = validate_artifact(
        _FIXTURE, ArtifactName.PREPROCESS_OUTPUT, version="1.2.0"
    )
    violations = [
        (v.violation_code, v.field_path, v.reason) for v in outcome.violations
    ]
    assert outcome.passed, violations
    assert outcome.counts.error == 0


def test_confidence_null_fails_against_v1_0_0():
    """Regression guard: the v1.0.0 schema still rejects null — confirms the
    widening is actually scoped to v1.2.0+ and didn't accidentally retrofit."""
    outcome = validate_artifact(
        _FIXTURE, ArtifactName.PREPROCESS_OUTPUT, version="1.0.0"
    )
    # Fixture stamped "1.2.0" → version-compat check fires first, or the schema
    # rejects null. Either way, validation must NOT pass against v1.0.0.
    assert not outcome.passed, (
        "v1.0.0 schema should still reject confidence=null; if this passes, "
        "the v1.0.0 schema was accidentally edited (v1.0.0 is frozen)."
    )


def test_loader_latest_resolves_to_v1_2_0_or_newer():
    """Guard: the AMENDMENTS sequence is in place — latest contract set picks
    up the confidence-null widening without an explicit version pin."""
    cs = load_contract_set()
    major, minor, _ = (int(p) for p in cs.version.split("."))
    assert (major, minor) >= (1, 2), (
        f"expected latest contract set >= 1.2.0 but got {cs.version}; "
        "AMENDMENTS v1.2.0 directory must exist and be the newest v*.*.* "
        "subdir under contracts/stage1_vendor_identity/."
    )
