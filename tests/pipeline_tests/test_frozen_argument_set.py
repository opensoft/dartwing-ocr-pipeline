"""Amended argument-set test: pre-011 (frozen 002) + 011 amendment surface.

The 002 contract froze the original 11 flags; the 011 contract amendment
adds 11 new flags (per-stage profile, stack preset, slice, documents-file,
on-failure, CPU/Jetson Ollama lane URLs). This test asserts the union
without permitting silent drift in either direction.

Spec FR-002, FR-003, FR-004, FR-004A, FR-016, FR-017, FR-023, FR-028.
Contract: specs/011-stage-runtime-profiles/contracts/cli-contract.md.
"""
from __future__ import annotations

from dartwing_ocr.pipeline.cli import _build_parser

# Frozen 002 surface -- preserved verbatim by FR-002.
_FROZEN_002 = {
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

# 011 amendment surface (FR-003 / FR-004 / FR-004A / FR-016 / FR-017 /
# FR-023 / FR-028).
_AMENDMENT_011 = {
    "--preprocess-profile",
    "--extract-profile",
    "--routing-profile",
    "--final-payload-profile",
    "--stack-preset",
    "--start-at",
    "--stop-after",
    "--documents-file",
    "--on-failure",
    "--ollama-cpu-url",
    "--ollama-jetson-url",
}

# Feature 016 amendment (FR-002 / R-016.1 / contracts/cli-contract.md §1):
# `--gpu-warmup` opt-in for the explicit GPU warmup pass on
# ppstructurev3@gpu. Orthogonal to all other flags.
_AMENDMENT_016 = {
    "--gpu-warmup",
}

# Feature 017 amendment (FR-002 / FR-005 / FR-006 / R-017.1 /
# contracts/cli-contract.md §1): two closed-vocabulary preset axes for the
# ppstructurev3@gpu lane. Orthogonal to all other flags.
_AMENDMENT_017 = {
    "--module-set",
    "--det-rec-variant",
}

# Feature 018 amendment (FR-001 / FR-004 / R-018.1 /
# contracts/cli-contract.md §1): two closed-vocabulary preset axes for the
# ppstructurev3@gpu lane (DPI + region strategy). Orthogonal to all other
# flags. US1 (T009) lands `--raster-profile`; US2 (T019) lands
# `--region-strategy`.
_AMENDMENT_018 = {
    "--raster-profile",
    "--region-strategy",
}

_EXPECTED = (
    _FROZEN_002 | _AMENDMENT_011 | _AMENDMENT_016 | _AMENDMENT_017 | _AMENDMENT_018
)


def _collect_run_subparser_flags() -> set[str]:
    parser = _build_parser()
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
    return flags


def test_run_subparser_exposes_exactly_frozen_plus_amendment_arguments():
    flags = _collect_run_subparser_flags()
    extra = flags - _EXPECTED
    missing = _EXPECTED - flags
    assert flags == _EXPECTED, f"mismatch: extra={extra}, missing={missing}"


def test_frozen_002_subset_present_unchanged():
    """FR-002: every 002 flag MUST still be accepted."""
    flags = _collect_run_subparser_flags()
    missing_002 = _FROZEN_002 - flags
    assert not missing_002, f"002 flags removed by 011: {missing_002}"


def test_amendment_011_subset_present():
    """FR-003 / FR-004 / FR-004A / FR-016 / FR-017 / FR-023 / FR-028."""
    flags = _collect_run_subparser_flags()
    missing_011 = _AMENDMENT_011 - flags
    assert not missing_011, f"011 amendment flags missing: {missing_011}"
