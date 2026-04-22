"""US1 AC#5 — status is one of {success, partial, failure}; on clean happy path it must be success with no warnings."""

from __future__ import annotations

from pathlib import Path


def test_ac5_status_success_implies_no_hard_warning(
    us1_happy_folder: Path, run_extractor, load_output
) -> None:
    rc = run_extractor(us1_happy_folder, us1_happy_folder / "voter_config.yaml")
    assert rc == 0

    payload = load_output(us1_happy_folder)
    assert payload["status"] in {"success", "partial", "failure"}

    # Happy-path clean fixture: every field has grounded evidence and no JSON repair
    # was needed. Reconciliation must produce status=success and no warnings.
    assert payload["status"] == "success", (
        f"expected status=success for the clean happy-path fixture; "
        f"got {payload['status']!r} with warnings={payload['warnings']!r} "
        f"and extraction_notes={payload['extraction_notes']!r}"
    )
    assert payload["warnings"] == []
