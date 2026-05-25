"""Run-correlation identifier (R-023.6)."""

from __future__ import annotations

import uuid


def new_run_id() -> str:
    """Return a fresh UUID4 string (36 chars, lowercase hex, hyphenated)."""
    return str(uuid.uuid4())


def prefix_for(run_id: str) -> str:
    """Return the 8-char stderr prefix — the UUID's first hex segment.

    For ``run_id = "a1b2c3d4-1234-5678-9abc-def012345678"`` this returns
    ``"a1b2c3d4"``. Same value across every stderr line within the same run.
    """
    return run_id[:8]
