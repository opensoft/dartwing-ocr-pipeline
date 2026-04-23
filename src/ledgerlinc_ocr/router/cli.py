"""CLI surface for ``python -m ledgerlinc_ocr.router``.

Maps the exit-code taxonomy pinned in ``contracts/cli-contract.md``:

    0  success
    2  malformed input (missing / unreadable / schema-invalid / version drift)
    3  internal error (assembled artifact failed routing_decision.schema.json)
    1  unexpected exception

On success emits a single JSON line on stdout for machine consumption.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from ledgerlinc_ocr.router.errors import (
    ContractAssertionError,
    MalformedInputError,
    MissingInputError,
    UnreadableInputError,
    VersionDriftError,
)
from ledgerlinc_ocr.router.pipeline import run
from ledgerlinc_ocr.router.version import POLICY_VERSION, build_pipeline_version

EXIT_SUCCESS = 0
EXIT_UNEXPECTED = 1
EXIT_MALFORMED_INPUT = 2
EXIT_INTERNAL = 3


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ledgerlinc_ocr.router",
        description=(
            "Stage 1 deterministic router: consume edge_extraction_output.json "
            "and emit a schema-valid routing_decision.json next to it."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    route = sub.add_parser(
        "route",
        help=(
            "Route one per-document folder. Writes "
            "<PATH>/routing_decision.json."
        ),
    )
    route.add_argument(
        "path",
        type=Path,
        help="Per-document folder containing edge_extraction_output.json.",
    )
    route.add_argument(
        "--input-file",
        default="edge_extraction_output.json",
        help="Name of the input JSON inside <PATH> (default: %(default)s).",
    )
    route.add_argument(
        "--pipeline-version",
        default=build_pipeline_version(),
        help="Pipeline version recorded in the artifact (default: %(default)s).",
    )
    route.add_argument(
        "--policy-version",
        default=POLICY_VERSION,
        help="Policy version recorded in the artifact (default: %(default)s).",
    )
    return parser


def _route(args: argparse.Namespace) -> int:
    folder: Path = args.path
    if not folder.exists() or not folder.is_dir():
        print(
            f"error: folder does not exist or is not a directory: {folder}",
            file=sys.stderr,
        )
        return EXIT_MALFORMED_INPUT

    try:
        path, artifact = run(
            folder,
            pipeline_version=args.pipeline_version,
            policy_version=args.policy_version,
            input_file=args.input_file,
        )
    except (MissingInputError, UnreadableInputError, MalformedInputError,
            VersionDriftError) as exc:
        print(f"error: {exc.human_message}", file=sys.stderr)
        return EXIT_MALFORMED_INPUT
    except ContractAssertionError as exc:
        print(f"internal error: {exc.human_message}", file=sys.stderr)
        return EXIT_INTERNAL
    except Exception:  # noqa: BLE001 — surface anything unexpected
        traceback.print_exc()
        return EXIT_UNEXPECTED

    json.dump(
        {
            "status": "ok",
            "document_id": artifact["document_id"],
            "decision": artifact["decision"],
            "artifact": str(path.resolve()),
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return EXIT_SUCCESS


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "route":
        return _route(args)
    parser.error(f"unknown command: {args.command}")
    return EXIT_UNEXPECTED  # unreachable — parser.error exits


if __name__ == "__main__":  # pragma: no cover — thin shim
    sys.exit(main())
