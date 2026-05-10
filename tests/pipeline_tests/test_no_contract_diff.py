"""Feature 017 (T034 / US5 / FR-019 / SC-010): CPU-safe contract
immutability test.

Asserts that this feature's PR does not modify any file under
`contracts/stage1_vendor_identity/` (the four canonical artifact
schemas + `contract_set.json` + `AMENDMENTS.md`). If a change is
detected, fail with a message naming the changed file and pointing to
the FR-020 escape hatch (must-update of data-model.md + research.md +
AMENDMENTS).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _repo_root() -> Path:
    """Walk up from this test file to find the repo root (the directory
    containing `contracts/` and `pyproject.toml`)."""
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        if (ancestor / "contracts" / "stage1_vendor_identity").is_dir():
            return ancestor
    raise RuntimeError("Could not locate repo root (looking for contracts/stage1_vendor_identity/)")


def _resolve_diff_target(root: Path) -> str:
    """Return the first ref from a priority list that resolves locally.
    Tries ``origin/main`` first (PR CI almost always has it), then
    ``main`` (developer checkouts). Skips the test when neither
    resolves — this guard is intended for CI runs against a PR base."""
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
    pytest.skip(
        "neither origin/main nor main resolves in this checkout; "
        "this guard is intended for CI runs against a PR base"
    )


def test_no_diff_against_main_in_canonical_contracts_directory() -> None:
    """Per SC-010 / FR-019: this feature must not change any file under
    `contracts/stage1_vendor_identity/`. Verified via `git diff` against
    the resolved base ref (``origin/main`` in CI, ``main`` for local
    developer checkouts).

    If this test fails, the feature has either: (a) accidentally
    touched a contract file (revert the change), or (b) intentionally
    needs a contract change — in which case the FR-020 escape hatch
    applies (update data-model.md + research.md + AMENDMENTS.md, and
    this test should then be updated to reflect the new contract set
    version).
    """
    root = _repo_root()
    try:
        target_ref = _resolve_diff_target(root)
    except FileNotFoundError:
        pytest.skip("git not installed")

    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            target_ref,
            "--",
            "contracts/stage1_vendor_identity/",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"git diff against {target_ref!r} failed: rc={result.returncode} "
        f"stderr={result.stderr.strip()!r}"
    )

    changed_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert not changed_files, (
        f"feature 017 must not modify contracts/stage1_vendor_identity/ "
        f"(SC-010 / FR-019). Changed files (vs {target_ref}): {changed_files}\n"
        f"If a contract change is needed, follow the FR-020 escape "
        f"hatch: update data-model.md + research.md + "
        f"contracts/stage1_vendor_identity/AMENDMENTS.md."
    )
