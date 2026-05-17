"""Shared git utilities for pipeline tests that diff the working tree
against the PR base ref.

Two helpers live here so the same code does not get re-copied into each
feature's regression test (features 017, 020, ...). Both fail LOUDLY
when the environment is wrong: a missing ``main``/``origin/main`` is a
CI misconfiguration that would otherwise let a contract-leak slip
through under a "skipped" mask. The fix in CI is one line —
``git fetch --no-tags origin main:refs/remotes/origin/main`` — so we
prefer a noisy failure to a silent skip.
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

    FAILS the test if neither ref resolves. A hollow guard (silent skip)
    would let a contracts-immutability regression land undetected on
    shallow-clone CI variants; a loud failure surfaces the
    ``git fetch origin main:refs/remotes/origin/main`` fix immediately.
    """
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
    pytest.fail(
        "neither origin/main nor main resolves in this checkout. "
        "This contracts-immutability guard requires a base ref. "
        "Fix in CI: `git fetch --no-tags --depth=1 origin "
        "main:refs/remotes/origin/main` before pytest. "
        "Locally: `git fetch origin main:main`."
    )
