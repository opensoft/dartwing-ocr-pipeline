"""CLI argparse + main entry point for the GPU MVP demo (T016).

Exposes the closed 5-flag set per ``contracts/cli-contract.md``:

  --check-only
  --document-folder <PATH>
  --voter-config <PATH>
  --preset <NAME>           (header-first-v1 | full-ocr)
  --with-evaluator

Plus the two exempt non-run flags: --help and --version.

``main()`` returns the exit code (it does NOT call ``sys.exit`` — that keeps
``__main__`` thin and ``main()`` directly testable). The orchestrator is wired
in at T035 once the readiness runner + phase composition land in Phase 3.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from dartwing_ocr.gpu_demo.enums import (
    DEFAULT_DOCUMENT_FOLDER,
    DEFAULT_PRESET,
    SUPPORTED_PRESETS,
)
from dartwing_ocr.gpu_demo.exit_codes import ExitCode
from dartwing_ocr.gpu_demo.version import get_pipeline_version


def build_parser() -> argparse.ArgumentParser:
    """Build the closed 5-flag argparse parser for the demo CLI."""
    parser = argparse.ArgumentParser(
        prog="dartwing-gpu-demo",
        description=(
            "GPU MVP demo: runs the workstation full-workstation GPU lane "
            "(Paddle ROCm + host Ollama) against a stage 1 fixture and emits "
            "a single-line DemoRunReport JSON on stdout."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Run readiness checks only (FR-016 checks 1-6); skip pipeline. "
            "Ignores --document-folder, --preset, --with-evaluator."
        ),
    )
    parser.add_argument(
        "--document-folder",
        type=Path,
        default=Path(DEFAULT_DOCUMENT_FOLDER),
        help=(
            "Per-document folder containing source.pdf (and where the 4 "
            f"canonical artifacts will be written). Default: {DEFAULT_DOCUMENT_FOLDER}"
        ),
    )
    parser.add_argument(
        "--voter-config",
        type=Path,
        default=None,
        help=(
            "Explicit voter-config YAML path. Default: feature 005/021 "
            "auto-discovery."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=SUPPORTED_PRESETS,
        default=DEFAULT_PRESET,
        help=f"Preprocessing preset. Default: {DEFAULT_PRESET}",
    )
    parser.add_argument(
        "--with-evaluator",
        action="store_true",
        help=(
            "Invoke feature 022 semantic-quality evaluator after the pipeline "
            "(off by default; warn-and-skip if sidecar missing)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"dartwing-gpu-demo {get_pipeline_version()}",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Demo CLI entry point. Returns one of the closed ExitCode values (T035).

    Delegates to the orchestrator (T034). ``main()`` does NOT call
    ``sys.exit`` so tests can invoke it directly and assert the return value.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Lazy import keeps argparse / --help / --version fast and avoids loading
    # the orchestrator's transitive imports (httpx, packaging, etc.) for
    # those cheap paths.
    from dartwing_ocr.gpu_demo.orchestrator import run

    return run(args)
