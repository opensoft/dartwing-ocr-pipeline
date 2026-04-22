"""argparse CLI for the final-payload assembler.

See `contracts/cli-contract.md` for the stability guarantees.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ledgerlinc_ocr.assembler import pipeline
from ledgerlinc_ocr.assembler.errors import (
    EXIT_OK,
    EXIT_UNEXPECTED,
    AssemblerError,
    InputRejectedError,
    InternalError,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledgerlinc-assemble",
        description="Stage 1 final structured payload assembler (009-final-payload).",
    )
    p.add_argument("--document-folder", type=Path, required=True)
    p.add_argument("--pipeline-version", type=str, default=None)
    return p


def _emit_error(kind: str, message: str) -> None:
    print(
        json.dumps({"status": "error", "kind": kind, "message": message}),
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    invocation = pipeline.Invocation(
        document_folder=args.document_folder,
        pipeline_version=args.pipeline_version,
    )

    try:
        pipeline.run(invocation)
    except (InputRejectedError, InternalError) as exc:
        _emit_error(exc.kind, str(exc))
        return exc.exit_code
    except AssemblerError as exc:  # defensive — any new subclass
        _emit_error(exc.kind, str(exc))
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - defensive
        _emit_error("unexpected", f"{type(exc).__name__}: {exc}")
        return EXIT_UNEXPECTED

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
