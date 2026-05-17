"""Feature 020 / T049 / US6 (SC-010 / FR-020):
canonical-contracts immutability guard for this feature's PR.

FR-020: feature 020 MUST NOT touch any file under
``contracts/stage1_vendor_identity/``. The four canonical artifact
schemas and ``contract_set.json`` are frozen at the v1.2.0 contract set;
schema-evolution lives in ``contracts/stage1_vendor_identity/AMENDMENTS.md``
and is out of scope for this feature.

This test replicates the pattern of ``test_no_contract_diff.py`` (feature
017) but is owned by feature 020's US6 regression bundle. It runs as a
CPU-safe check on every PR. It is intentionally NOT redundant with
feature 017's copy — each feature owns its own contracts-immutability
guard so a future contract leak attributable to this feature lands on
this test's stack trace specifically.

Also asserts SC-010 / FR-020 cont: ``contract_set_version`` on the
working tree reads the same string as on the main branch.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


_CONTRACT_SET_VERSION_PATH = (
    "contracts/stage1_vendor_identity/v1.2.0/contract_set.json"
)


def _repo_root() -> Path:
    """Walk up from this test file to the repo root (the directory that
    contains ``contracts/stage1_vendor_identity/``)."""
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        if (ancestor / "contracts" / "stage1_vendor_identity").is_dir():
            return ancestor
    raise RuntimeError(
        "Could not locate repo root (looking for "
        "contracts/stage1_vendor_identity/)"
    )


def _resolve_diff_target(root: Path) -> str:
    """Return the first ref from a priority list that resolves locally.
    Tries ``origin/main`` first (PR CI typically has it), then ``main``
    (developer checkouts). Skips when neither resolves (CI variants that
    do not fetch ``main`` cannot run this guard)."""
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
        "this contracts-immutability guard requires a base ref. "
        "Re-run with `git fetch origin main:main` (or in CI against "
        "a PR base)."
    )


def test_feature_020_changes_no_canonical_contract_file() -> None:
    """SC-010 / FR-020: no file under
    ``contracts/stage1_vendor_identity/`` changes on this feature's PR
    relative to ``main``.

    If this test fails, either: (a) revert the change to the contracts
    directory, or (b) intentionally evolve the contract — which routes
    through ``contracts/stage1_vendor_identity/AMENDMENTS.md`` and is
    OUT OF SCOPE for feature 020 (the gate is observability over
    existing artifacts, never a schema change).
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
    changed_files = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]
    assert not changed_files, (
        "SC-010 / FR-020 violation: feature 020 must not modify any file "
        f"under contracts/stage1_vendor_identity/. Changed files (vs "
        f"{target_ref}): {changed_files}\n"
        "Schema evolution belongs in AMENDMENTS.md, not in feature 020."
    )


def test_contract_set_version_unchanged_vs_main() -> None:
    """FR-020: ``contract_set_version`` on the working tree reads the
    same string as on the base ref (``main`` / ``origin/main``).

    Read the JSON on each side independently so a reformat that doesn't
    change the version string still passes this version-string check —
    the broader file-level diff guard above catches the reformat
    separately.
    """
    root = _repo_root()
    try:
        target_ref = _resolve_diff_target(root)
    except FileNotFoundError:
        pytest.skip("git not installed")

    # Local version (working tree).
    local_path = root / _CONTRACT_SET_VERSION_PATH
    if not local_path.exists():
        pytest.skip(
            f"working-tree {_CONTRACT_SET_VERSION_PATH} not found; "
            "contract set may have been renamed — investigate."
        )
    local_obj = json.loads(local_path.read_text(encoding="utf-8"))
    local_version = local_obj.get("contract_set_version")
    assert isinstance(local_version, str) and local_version, (
        f"working-tree {_CONTRACT_SET_VERSION_PATH} missing "
        "contract_set_version string"
    )

    # Base-ref version (committed on target_ref).
    show_result = subprocess.run(
        ["git", "show", f"{target_ref}:{_CONTRACT_SET_VERSION_PATH}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if show_result.returncode != 0:
        pytest.skip(
            f"contract_set.json not available on {target_ref}: "
            f"{show_result.stderr.strip()!r}"
        )
    base_obj = json.loads(show_result.stdout)
    base_version = base_obj.get("contract_set_version")
    assert isinstance(base_version, str) and base_version, (
        f"{target_ref}:{_CONTRACT_SET_VERSION_PATH} missing "
        "contract_set_version string"
    )

    assert local_version == base_version, (
        f"FR-020 violation: contract_set_version on the working tree "
        f"({local_version!r}) differs from {target_ref} "
        f"({base_version!r}). Feature 020 must not bump the contract "
        "set version — schema evolution routes through "
        "contracts/stage1_vendor_identity/AMENDMENTS.md."
    )
