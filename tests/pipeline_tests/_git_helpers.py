"""Shared git utilities for pipeline tests that diff the working tree
against the PR base ref.

Two helpers live here so the same code does not get re-copied into each
feature's regression test (features 017, 020, ...).

**Skip semantics (Copilot review feedback):** these helpers SKIP rather
than fail when the environment cannot support the guard. The skip
message is verbose and actionable — it always names the exact CI fix
(`git fetch --no-tags --depth=1 origin main:refs/remotes/origin/main`)
so a hollow skip in CI surfaces immediately on the first PR that
modifies a contract. The earlier-cycle concern about silent skips is
addressed by message clarity, not by hard-failing on shallow-clone CI
which would block common repo configurations.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def repo_root() -> Path:
    """Walk up from this module to the repo root (directory containing
    ``contracts/stage1_vendor_identity/``)."""
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        if (ancestor / "contracts" / "stage1_vendor_identity").is_dir():
            return ancestor
    raise RuntimeError(
        "Could not locate repo root (looking for "
        "contracts/stage1_vendor_identity/)"
    )


def resolve_diff_target(root: Path) -> str:
    """Return the first ref from a priority list that resolves locally:
    ``origin/main`` first (PR CI), then ``main`` (developer checkouts).

    Skips the test with a clear, actionable message when the
    environment cannot resolve a base ref — either git is not on PATH
    or neither candidate ref exists locally (shallow-clone CI). The
    skip message always includes the exact CI fix so the guard is one
    config line away from running.
    """
    try:
        for ref in ("origin/main", "main"):
            result = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet", ref],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return ref
    except FileNotFoundError:
        pytest.skip(
            "git binary not on PATH. Install git to enable this "
            "contracts-immutability guard."
        )
    pytest.skip(
        "Neither origin/main nor main resolves in this checkout. "
        "To enable this contracts-immutability guard, fetch main first. "
        "In CI: `git fetch --no-tags --depth=1 origin "
        "main:refs/remotes/origin/main`. "
        "Locally: `git fetch origin main:main`."
    )
