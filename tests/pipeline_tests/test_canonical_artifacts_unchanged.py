"""Feature 020 / T049 / US6 (SC-006 / SC-010 / FR-020):
canonical-contracts immutability guard for this feature's PR.

FR-020 / SC-010: feature 020 MUST NOT touch any file under
``contracts/stage1_vendor_identity/``. The four canonical artifact
schemas and ``contract_set.json`` are frozen at the v1.2.0 contract set;
schema-evolution lives in ``contracts/stage1_vendor_identity/AMENDMENTS.md``
and is out of scope for this feature.

SC-006: feature 020 MUST NOT modify any committed corpus baseline file
under ``tests/stage1_vendor_identity/inv_*/`` (source.pdf, expected.json,
preprocess_output.json, notes.md). README and .gitkeep are doc-only and
not in scope.

These tests replicate the pattern of ``test_no_contract_diff.py`` (feature
017) but are owned by feature 020's US6 regression bundle. They run as
CPU-safe checks on every PR. They are intentionally NOT redundant —
each feature owns its own immutability guard so a future leak
attributable to this feature lands on this test's stack trace
specifically.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from tests.pipeline_tests._git_helpers import repo_root, resolve_diff_target


_CONTRACT_SET_VERSION_PATH = (
    "contracts/stage1_vendor_identity/v1.2.0/contract_set.json"
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
    root = repo_root()
    target_ref = resolve_diff_target(root)

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


def test_feature_020_changes_no_corpus_baseline_file() -> None:
    """SC-006: feature 020 MUST NOT modify any committed corpus baseline
    file under ``tests/stage1_vendor_identity/inv_*/`` relative to
    ``main``. Per-document folders hold the frozen ground truth
    (source.pdf, expected.json, preprocess_output.json, notes.md) for
    the evaluator harness; a regression that re-baselines them would
    silently change pass/fail outcomes.

    The corpus README and .gitkeep at the directory root are NOT in
    scope — only files under ``inv_*/`` subfolders.
    """
    root = repo_root()
    target_ref = resolve_diff_target(root)

    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            target_ref,
            "--",
            "tests/stage1_vendor_identity/inv_*/",
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
        "SC-006 violation: feature 020 must not modify any committed "
        "corpus baseline file under tests/stage1_vendor_identity/inv_*/. "
        f"Changed files (vs {target_ref}): {changed_files}\n"
        "Corpus re-baselining is a deliberate, separately-reviewed action "
        "(see docs/stage1-vendor-identity/labeling-guide.md) — never a "
        "side effect of a feature implementation."
    )


def test_contract_set_version_unchanged_vs_main() -> None:
    """FR-020: ``contract_set_version`` on the working tree reads the
    same string as on the base ref (``main`` / ``origin/main``).

    Read the JSON on each side independently so a reformat that doesn't
    change the version string still passes this version-string check —
    the broader file-level diff guard above catches the reformat
    separately.
    """
    root = repo_root()
    target_ref = resolve_diff_target(root)

    local_path = root / _CONTRACT_SET_VERSION_PATH
    assert local_path.exists(), (
        f"working-tree {_CONTRACT_SET_VERSION_PATH} missing. The "
        "contract set has been renamed or removed — investigate before "
        "merging this PR."
    )
    local_obj = json.loads(local_path.read_text(encoding="utf-8"))
    local_version = local_obj.get("contract_set_version")
    assert isinstance(local_version, str) and local_version, (
        f"working-tree {_CONTRACT_SET_VERSION_PATH} missing "
        "contract_set_version string"
    )

    show_result = subprocess.run(
        ["git", "show", f"{target_ref}:{_CONTRACT_SET_VERSION_PATH}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert show_result.returncode == 0, (
        f"contract_set.json not available on {target_ref}: "
        f"{show_result.stderr.strip()!r}. If the file was intentionally "
        "renamed, update this test together with the rename — a missing "
        "base-ref version is NOT a valid skip condition."
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
