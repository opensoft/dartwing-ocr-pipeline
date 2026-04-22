"""CLI contract: exit code 3 on assembled-artifact schema failure.

``contracts/cli-contract.md`` pins exit 3 to "internal error — the
assembled routing_decision failed routing_decision.schema.json". The CLI
maps ``ContractAssertionError`` to exit 3 and prints an ``internal error:``
prefix on stderr.

No fixture reproduces this path naturally (by design — the router should
never emit a schema-invalid artifact), so we force a validator failure by
patching the ``validate_artifact`` call INSIDE the artifact module (the
public validator boundary that the exit-3 contract actually depends on).
Patching at this layer — rather than at a private pipeline helper —
means any safe refactor that keeps the contract intact will keep the
test passing.

Called in-process via ``cli.main`` rather than subprocess so the patch is
visible to the code under test.
"""
from __future__ import annotations

from pathlib import Path

from ledgerlinc_ocr.validator import ValidationOutcome
from ledgerlinc_ocr.validator.report import (
    Severity,
    ValidationOutcomeCounts,
    Violation,
    ViolationCode,
)


def _failed_outcome() -> ValidationOutcome:
    v = Violation(
        severity=Severity.ERROR,
        target="routing_decision",
        field_path="$.policy_version",
        violation_code=ViolationCode.SCHEMA_REQUIRED_MISSING,
        reason="required property 'policy_version' is missing (injected)",
    )
    return ValidationOutcome(
        contract_set_version_checked="1.0.0",
        target_summary="routing_decision (injected failure)",
        passed=False,
        violations=[v],
        warnings=[],
        counts=ValidationOutcomeCounts(error=1, warning=0),
    )


def test_cli_returncode_3_on_assembled_schema_failure(
    tmp_path: Path, monkeypatch, stage_fixture, capsys
):
    from ledgerlinc_ocr.router import artifact as artifact_mod
    from ledgerlinc_ocr.router.cli import main as cli_main

    folder = stage_fixture(tmp_path, "clean_explicit_name_full_identity.json")

    # Patch the validator at the public boundary that ``artifact.py``
    # imports and calls. This is the exact hook the exit-3 contract
    # depends on — any code path that produces a failed ``ValidationOutcome``
    # from validate_artifact MUST surface as exit 3.
    monkeypatch.setattr(
        artifact_mod, "validate_artifact", lambda *a, **kw: _failed_outcome()
    )

    rc = cli_main(["route", str(folder)])
    assert rc == 3, (
        f"expected exit 3 (internal error) on failed validate_artifact; "
        f"got {rc}. Exit 2 would mean the CLI misclassified a code/contract "
        f"drift as malformed input; exit 1 would mean it leaked the "
        f"ContractAssertionError as an unexpected exception."
    )
    captured = capsys.readouterr()
    assert "internal error" in captured.err.lower(), (
        f"exit 3 must print an 'internal error:' diagnostic on stderr; "
        f"got: {captured.err!r}"
    )
    # No routing_decision.json must be visible — atomic-write path fails
    # at the validator gate before os.replace.
    assert not (folder / "routing_decision.json").exists(), (
        "exit 3 must not leave a schema-invalid routing_decision.json on disk"
    )
    # And no leftover tempfiles — ``artifact.py`` unlinks on validator
    # failure. A leaked ``.routing_decision.*.json.tmp`` would mean the
    # cleanup path in ``assemble_and_write`` regressed, which FR-022's
    # "no writes outside the target folder" guarantee silently depends on.
    leftovers = sorted(
        p.name for p in folder.iterdir() if p.name.startswith(".routing_decision.")
    )
    assert leftovers == [], (
        f"exit 3 must unlink the sibling tempfile; found leftovers: {leftovers}"
    )
