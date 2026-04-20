"""T041: live argparse parser exposes exactly the frozen argument set."""
from __future__ import annotations

from ledgerlinc_ocr.pipeline.cli import _build_parser

_EXPECTED = {
    "--input",
    "--document-folder",
    "--output-dir",
    "--document-id",
    "--overwrite",
    "--pipeline-version",
    "--policy-version",
    "--contract-set-version",
    "--ollama-url",
    "--log-level",
    "--timeout",
}


def test_run_subparser_exposes_exactly_frozen_arguments():
    parser = _build_parser()
    # Locate the `run` subparser.
    run = None
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices and "run" in action.choices:
            run = action.choices["run"]
            break
    assert run is not None, "run subcommand missing"

    flags: set[str] = set()
    for action in run._actions:
        if action.dest == "help":
            continue
        for opt in action.option_strings:
            if opt.startswith("--"):
                flags.add(opt)

    assert flags == _EXPECTED, f"mismatch: extra={flags - _EXPECTED}, missing={_EXPECTED - flags}"
