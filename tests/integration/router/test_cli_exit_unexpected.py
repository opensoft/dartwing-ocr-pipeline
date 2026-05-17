"""CLI contract: exit code 1 on genuinely unexpected exceptions.

``contracts/cli-contract.md`` pins exit 1 to "Any unexpected exception
(stack trace on stderr)". The CLI's ``except Exception`` branch in
``cli.py`` is intentionally broad — it catches everything that isn't one
of the typed router errors and prints a traceback so a human can diagnose.

Without a test, a future refactor that narrows the final ``except`` (or
lets an exception escape the CLI entry point altogether — turning it into
a ``SystemExit`` with code ``>0`` but no traceback) would silently break
the operational contract that exit 1 is accompanied by enough stderr
context to file a bug report.

We force the path by patching ``pipeline.run`` to raise a bare
``RuntimeError`` — the simplest non-typed exception, the one the CLI
does NOT know how to classify.
"""
from __future__ import annotations

from pathlib import Path


def test_cli_returncode_1_on_unexpected_exception(
    tmp_path: Path, monkeypatch, stage_fixture, capsys
):
    from dartwing_ocr.router import cli as cli_mod
    from dartwing_ocr.router.cli import main as cli_main

    folder = stage_fixture(tmp_path, "clean_explicit_name_full_identity.json")

    def boom(*args, **kwargs):
        raise RuntimeError(
            "simulated unexpected failure (not a RouterError subclass)"
        )

    # Patch ``run`` at the name bound inside ``cli.py`` so the ``except
    # Exception`` in ``_route`` is exercised.
    monkeypatch.setattr(cli_mod, "run", boom)

    rc = cli_main(["route", str(folder)])
    assert rc == 1, (
        f"expected exit 1 (unexpected exception) on bare RuntimeError; "
        f"got {rc}. Exit 2 would mean the CLI silently reclassified an "
        f"unknown failure as malformed input; exit 3 would mean it treated "
        f"it as a schema drift. Both would hide the real bug."
    )
    captured = capsys.readouterr()
    # cli.py uses ``traceback.print_exc`` for this branch; the exception
    # type and message MUST both appear so a human can triage from logs.
    assert "RuntimeError" in captured.err, (
        f"exit 1 must print the exception class on stderr; got: {captured.err!r}"
    )
    assert "simulated unexpected failure" in captured.err, (
        f"exit 1 must print the exception message on stderr; "
        f"got: {captured.err!r}"
    )
    # Traceback marker — proof we went through ``traceback.print_exc``.
    assert "Traceback" in captured.err, (
        f"exit 1 must include a traceback; got: {captured.err!r}"
    )
    assert not (folder / "routing_decision.json").exists(), (
        "unexpected-exception path must not write routing_decision.json"
    )
