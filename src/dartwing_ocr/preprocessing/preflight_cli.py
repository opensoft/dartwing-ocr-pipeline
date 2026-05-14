"""Preflight CLI for `python -m dartwing_ocr.preprocessing.preflight` (T014).

Argparse front-door for the FR-001 preflight diagnostic. Produces the
dual-format readout per Research R-014.5 and Contracts §1.Stdout shape:
human-readable text section followed by exactly one trailing JSON line
(`kind:"preflight_readout"`). Exit code maps to FR-001 state per
Contracts §1.Exit codes table (0 / 10–14; 1 for argparse error;
2 for unhandled internal classifier error).

The standalone `python -m dartwing_ocr.preprocessing.preflight`
invocation dispatches to this module's `main` via the `__main__`
block at the bottom of `preflight.py` (T015). The package-level
`python -m dartwing_ocr.preprocessing` invocation continues to
dispatch to `preprocessing/cli.py:main` (the existing single-doc
preprocessing CLI) via the unchanged `__main__.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from dartwing_ocr.preprocessing.preflight import (
    classify,
    exit_code_for_state,
)


class _UsageErrorParser(argparse.ArgumentParser):
    """ArgumentParser whose usage errors exit with code 1 per Contracts §1.

    argparse's default `error()` calls `self.exit(2, ...)`, but the FR-001
    contract reserves exit code 2 for internal classifier crashes. Override
    `error()` to exit 1 instead. `--help` is handled by argparse internally
    via `SystemExit(0)` (it does NOT route through `error()`), so help
    output continues to exit 0.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    p = _UsageErrorParser(
        prog="python -m dartwing_ocr.preprocessing.preflight",
        description=(
            "Paddle GPU preflight diagnostic (feature 014). Classifies the "
            "current environment into one of six FR-001 states and emits a "
            "dual-format readout (human text + trailing JSON line)."
        ),
    )
    p.add_argument(
        "--no-init",
        action="store_true",
        help=(
            "Suppress step 6 (PPStructureV3 GPU construction). Steps 1–5 "
            "still execute. Use in network-restricted shells where the "
            "first-run PPStructureV3 weight download would fail. See "
            "docs/stage1-vendor-identity/paddle-gpu-preflight.md for "
            "fully-offline operation knobs (PADDLE_PDX_MODEL_SOURCE, "
            "PaddleX model_dir)."
        ),
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help=(
            "Suppress the human-readable text section; emit only the trailing "
            "JSON line on stdout."
        ),
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        # argparse exits via SystemExit: --help raises SystemExit(0) after
        # printing help to stdout, and our _UsageErrorParser.error() calls
        # self.exit(1, ...) which raises SystemExit(1) after writing the
        # usage diagnostic to stderr. Catch both so main(...) returns the
        # integer exit code instead of propagating SystemExit, which keeps
        # the function safe to call from Python tests/library callers.
        # Defensive cast: argparse normally emits int codes, but SystemExit
        # tolerates non-int payloads — coerce anything non-int to 1 (usage
        # error) to keep the CLI contract integer-shaped.
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    try:
        readout = classify(attempt_ppstructurev3_init=not args.no_init)
    except Exception as exc:  # noqa: BLE001 - last-ditch internal error path
        print(
            f"preflight: internal error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    if not args.quiet:
        print(readout.to_text())
    print(
        json.dumps(
            readout.to_json_dict(),
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
    return exit_code_for_state(readout.state)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
