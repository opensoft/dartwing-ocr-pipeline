"""argparse CLI for the preprocessing slice (research Decision 9)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ledgerlinc_ocr.preprocessing import pipeline
from ledgerlinc_ocr.preprocessing.errors import (
    EXIT_INPUT_REJECTED,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
    EXIT_UNEXPECTED,
    ArtifactInvalidError,
    InputRejectedError,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledgerlinc-preprocess",
        description="Stage 1 PDF preprocessing (rasterize + OCR + layout + quality).",
    )
    p.add_argument("--document-folder", type=Path, required=True)
    p.add_argument("--source-file", type=str, default="source.pdf")
    p.add_argument("--write-page-images", action="store_true")
    p.add_argument("--pipeline-version", type=str, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    invocation = pipeline.Invocation(
        document_folder=args.document_folder,
        source_file=args.source_file,
        write_page_images=args.write_page_images,
        pipeline_version=args.pipeline_version,
    )

    try:
        out_path = pipeline.run(invocation)
        with out_path.open("r", encoding="utf-8") as f:
            written = json.load(f)
    except InputRejectedError as exc:
        print(
            json.dumps({"status": "error", "kind": "input_rejected", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INPUT_REJECTED
    except ArtifactInvalidError as exc:
        print(
            json.dumps({"status": "error", "kind": "artifact_invalid", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INTERNAL_ERROR
    except Exception as exc:
        print(
            json.dumps({"status": "error", "kind": "unexpected", "message": f"{type(exc).__name__}: {exc}"}),
            file=sys.stderr,
        )
        return EXIT_UNEXPECTED

    print(
        json.dumps(
            {
                "status": "ok",
                "document_id": written["document_id"],
                "artifact": str(out_path),
                "warnings": len(written.get("warnings", [])),
            }
        )
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
