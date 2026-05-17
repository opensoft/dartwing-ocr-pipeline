"""``dartwing-evidence-packet`` CLI.

Thin wrapper over :func:`dartwing_ocr.evidence_packet.assemble_from_folder`.
Exit-code mapping is defined in
``specs/004-evidence-packet-assembly/contracts/cli-contract.md``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from dartwing_ocr.evidence_packet import (
    PacketInvalid,
    PreprocessInputInvalid,
    PreprocessInputMissing,
    assemble_from_folder,
)
from dartwing_ocr.evidence_packet.version import CONTRACT_SET_VERSION

_EXIT_OK = 0
_EXIT_UNEXPECTED = 1
_EXIT_INPUT_MISSING = 2
_EXIT_INPUT_INVALID = 3
_EXIT_PACKET_INVALID = 4
_EXIT_PERSISTENCE_FAILED = 5

_LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"
_PACKAGE_LOGGER = "dartwing_ocr"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dartwing-evidence-packet",
        description=(
            "Assemble an evidence packet from a per-document folder containing "
            "preprocess_output.json. Use -v to persist evidence_packet.json."
        ),
    )
    parser.add_argument(
        "folder",
        help=(
            "Path to a per-document folder "
            "(e.g. tests/stage1_vendor_identity/inv_000_easy/)."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help=(
            "Raise the dartwing_ocr logger to DEBUG and persist "
            "evidence_packet.json into <folder>. Repeatable."
        ),
    )
    return parser


def _configure_logging(verbose: int) -> None:
    if verbose < 1:
        return
    logger = logging.getLogger(_PACKAGE_LOGGER)
    logger.setLevel(logging.DEBUG)
    already_installed = any(
        isinstance(h, logging.StreamHandler)
        and getattr(h, "_dartwing_cli", False)
        for h in logger.handlers
    )
    if not already_installed:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        handler._dartwing_cli = True  # type: ignore[attr-defined]
        logger.addHandler(handler)


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    sys.stdout.flush()


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    folder = Path(args.folder).resolve()
    persisted = logging.getLogger(_PACKAGE_LOGGER).isEnabledFor(logging.DEBUG)

    try:
        assemble_from_folder(folder)
    except PreprocessInputMissing as exc:
        _emit(
            {
                "status": "error",
                "kind": "input_missing",
                "folder": str(folder),
                "message": exc.message,
            }
        )
        return _EXIT_INPUT_MISSING
    except PreprocessInputInvalid as exc:
        _emit(
            {
                "status": "error",
                "kind": "input_invalid",
                "folder": str(folder),
                "message": exc.message,
            }
        )
        return _EXIT_INPUT_INVALID
    except PacketInvalid as exc:
        _emit(
            {
                "status": "error",
                "kind": "packet_invalid",
                "folder": str(folder),
                "message": exc.message,
            }
        )
        return _EXIT_PACKET_INVALID
    except OSError as exc:
        _emit(
            {
                "status": "error",
                "kind": "persistence_failed",
                "folder": str(folder),
                "message": str(exc),
            }
        )
        return _EXIT_PERSISTENCE_FAILED
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        _emit(
            {
                "status": "error",
                "kind": "unexpected",
                "folder": str(folder),
                "message": f"{type(exc).__name__}: {exc}",
            }
        )
        return _EXIT_UNEXPECTED

    _emit(
        {
            "status": "ok",
            "folder": str(folder),
            "persisted": persisted,
            "contract_set_version": CONTRACT_SET_VERSION,
        }
    )
    return _EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
