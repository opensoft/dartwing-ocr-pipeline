"""argparse CLI for the preprocessing slice (research Decision 9).

Feature 014 (T022): adds `--preprocess-profile` argument that accepts
the closed-set vocabulary from `pipeline.profiles` (default
``ppstructurev3@cpu``; ``ppstructurev3@gpu`` is the new opt-in lane).
Catches `GpuPrerequisiteError` raised by the inline gate in T021 and
exits with the FR-001-state-mapped exit code per Contracts §1.
"""

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
    EngineInitError,
    InputRejectedError,
)
from ledgerlinc_ocr.pipeline.profiles import (
    PPSTRUCTUREV3_CPU,
    ProfileValidationError,
    parse_profile,
)

# Feature 014 / VT-003: `preflight` types (GpuPrerequisiteError,
# exit_code_for_state) are imported lazily inside `main()`'s
# exception handler. Module-level import would break collection
# for unrelated tests when `preflight.py` is temporarily unavailable
# (T035 collection-time defensive path). The CPU path never raises
# GpuPrerequisiteError, so the lazy import never fires on CPU runs.


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledgerlinc-preprocess",
        description="Stage 1 PDF preprocessing (rasterize + OCR + layout + quality).",
    )
    p.add_argument("--document-folder", type=Path, required=True)
    p.add_argument("--source-file", type=str, default="source.pdf")
    p.add_argument("--write-page-images", action="store_true")
    p.add_argument("--pipeline-version", type=str, default=None)
    # Feature 014 (T022): closed-vocabulary preprocess-profile flag.
    # Default is ppstructurev3@cpu (FR-008); ppstructurev3@gpu is the
    # opt-in workstation lane gated by the FR-001 preflight (T021).
    p.add_argument(
        "--preprocess-profile",
        type=str,
        default=None,
        help=(
            "Preprocessing profile. Default: ppstructurev3@cpu. "
            "Workstation GPU lane: ppstructurev3@gpu (gated by preflight; "
            "see docs/stage1-vendor-identity/paddle-gpu-preflight.md). "
            "Other values are rejected per the closed vocabulary in "
            "ledgerlinc_ocr.pipeline.profiles."
        ),
    )
    return p


def _resolve_preprocess_lane(raw_value: str | None) -> str:
    """Parse --preprocess-profile through the closed vocabulary and
    return the lane string ('cpu' or 'gpu0')."""
    raw = raw_value or PPSTRUCTUREV3_CPU
    profile = parse_profile("preprocess", raw)
    if profile.lane == "cpu":
        return "cpu"
    if profile.lane == "gpu":
        # Single-doc CLI uses device 0 by default; multi-GPU is reserved
        # for future work per Out Of Scope and R-014.8.
        return "gpu0"
    raise ProfileValidationError(
        f"--preprocess-profile={raw!r}: unsupported lane {profile.lane!r} for preprocessing"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Lazy import: only fires when main() is actually called. Module-level
    # `import preprocessing.cli` (e.g., during pytest collection) does NOT
    # trigger this import, so a missing preflight.py does NOT break
    # collection of unrelated tests (analyze finding VT-003 / T035).
    from ledgerlinc_ocr.preprocessing.preflight import (
        GpuPrerequisiteError as _GpuPrerequisiteError,
        exit_code_for_state as _exit_code_for_state,
    )

    try:
        preprocess_lane = _resolve_preprocess_lane(args.preprocess_profile)
    except ProfileValidationError as exc:
        print(
            json.dumps({"status": "error", "kind": "input_rejected", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INPUT_REJECTED

    invocation = pipeline.Invocation(
        document_folder=args.document_folder,
        source_file=args.source_file,
        write_page_images=args.write_page_images,
        pipeline_version=args.pipeline_version,
        preprocess_lane=preprocess_lane,
    )

    try:
        out_path = pipeline.run(invocation)
        with out_path.open("r", encoding="utf-8") as f:
            written = json.load(f)
    except _GpuPrerequisiteError as exc:
        # Feature 014 (T022 / FR-009): name both the selected profile
        # and the FR-001 state in stderr; exit with the FR-001-state
        # exit code (10/11/12/13/14) per Contracts §1.
        print(
            f"error: --preprocess-profile=ppstructurev3@gpu: "
            f"{exc.state.value}; {exc.recommendation}",
            file=sys.stderr,
        )
        return _exit_code_for_state(exc.state)
    except InputRejectedError as exc:
        print(
            json.dumps({"status": "error", "kind": "input_rejected", "message": str(exc)}),
            file=sys.stderr,
        )
        return EXIT_INPUT_REJECTED
    except EngineInitError as exc:
        payload: dict[str, object] = {
            "status": "error",
            "kind": "engine_init_failed",
            "cause_class": exc.cause_class,
            "cause_module": exc.cause_module,
            "message": str(exc),
        }
        if exc.missing_weight is not None:
            payload["missing_weight"] = exc.missing_weight
        if exc.weight_hoster_url is not None:
            payload["weight_hoster_url"] = exc.weight_hoster_url
        print(json.dumps(payload), file=sys.stderr)
        return EXIT_INTERNAL_ERROR
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
