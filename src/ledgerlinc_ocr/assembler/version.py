"""Pipeline-version string for the final-payload assembler (research Decision 3)."""

from __future__ import annotations

SLICE_PREFIX = "009-final-payload"
SEMVER = "0.1.0"


def build_pipeline_version(semver: str = SEMVER) -> str:
    """Return `"009-final-payload@<semver>"`. Default matches current stage-1 policy."""
    return f"{SLICE_PREFIX}@{semver}"
