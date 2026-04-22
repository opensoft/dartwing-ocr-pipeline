"""CLI contract: exit code 3 on assembled-artifact schema failure.

``contracts/cli-contract.md`` pins exit 3 to "internal error — the
assembled routing_decision failed routing_decision.schema.json". The CLI
maps ``ContractAssertionError`` to exit 3 and prints an ``internal error:``
prefix on stderr.

No fixture reproduces this naturally (by design — the router should never
emit a schema-invalid artifact), so we inject a broken assembly step via
``monkeypatch`` on ``pipeline._build_artifact`` to force a violation and
confirm the CLI maps it to 3, not 1 (unexpected) or 2 (malformed input).

Called in-process via ``cli.main`` rather than subprocess so the monkey
patch is visible to the code under test.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_cli_returncode_3_on_assembled_schema_failure(
    tmp_path: Path, monkeypatch, stage_fixture, capsys
):
    from ledgerlinc_ocr.router import pipeline
    from ledgerlinc_ocr.router.cli import main as cli_main

    folder = stage_fixture(tmp_path, "clean_explicit_name_full_identity.json")

    original_build = pipeline._build_artifact

    def broken_build(**kwargs):
        artifact = original_build(**kwargs)
        # policy_version is ``required`` in routing_decision.schema.json, so
        # removing it guarantees a schema violation at the validator gate
        # inside ``assemble_and_write`` — which must surface as exit 3.
        del artifact["policy_version"]
        return artifact

    monkeypatch.setattr(pipeline, "_build_artifact", broken_build)

    rc = cli_main(["route", str(folder)])
    assert rc == 3, (
        f"expected exit 3 (internal error) on schema-invalid assembled "
        f"artifact; got {rc}. Exit 2 would mean the CLI misclassified a "
        f"code/contract drift as malformed input; exit 1 would mean it "
        f"leaked the ContractAssertionError as an unexpected exception."
    )
    captured = capsys.readouterr()
    assert "internal error" in captured.err.lower(), (
        f"exit 3 must print an 'internal error:' diagnostic on stderr; "
        f"got: {captured.err!r}"
    )
    # And no routing_decision.json must be visible — the atomic-write path
    # in artifact.py unlinks the tempfile before raising.
    assert not (folder / "routing_decision.json").exists(), (
        "exit 3 must not leave a schema-invalid routing_decision.json on disk"
    )
