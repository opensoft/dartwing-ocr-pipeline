"""T056 — feature 019 / 020 / 021 modules are untouched by feature 022.

Covers Principle I / FR-021 / FR-022 / FR-023 / FR-028 / FR-030 / MI-22.

This is a CI-style harness-side-only assertion: feature 022 lands the
deterministic semantic quality gate inside the evaluator/validator
subtrees ONLY. It must not touch any pipeline-side module:

- ``src/dartwing_ocr/preprocessing/`` (features 014–020)
- ``src/dartwing_ocr/extract/``       (feature 005)
- ``src/dartwing_ocr/router/``        (feature 008)
- ``src/dartwing_ocr/assembler/``     (feature 009)
- ``src/dartwing_ocr/pipeline/``      (features 011, 015, 021)

The test does three independent checks:

1. **Smoke import** — confirm the feature 019 OCR-only fallback module
   and the feature 021 GPU-MVP pipeline runner module both import
   without error and expose their public surface unchanged.

2. **Git-history diff** — assert no file under the five protected
   subtrees appears in the file-list of any feature-022 commit on this
   branch back to the merge base with ``main``. This is the strongest
   regression net (catches accidental edits even if they would not
   change runtime behavior).

3. **FR-030 negative grep** — assert no source file added or modified
   by feature 022 introduces the strings ``line_item``, ``line-item``,
   ``line items``, ``extract_lines``. Plus assert no v1.3.0 contract
   schema declares a ``line_items`` property, and assert
   ``contracts/stage1_vendor_identity/v1.3.0/final_structured_payload.schema.json``
   is byte-identical (SHA-256) to v1.2.0.

Pure CPU-only Python — no Paddle import, no network, no filesystem
writes (only reads). MI-1.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "dartwing_ocr"

# The five pipeline-side subtrees that feature 022 MUST NOT touch.
_PROTECTED_SUBTREES: tuple[str, ...] = (
    "src/dartwing_ocr/preprocessing/",
    "src/dartwing_ocr/extract/",
    "src/dartwing_ocr/router/",
    "src/dartwing_ocr/assembler/",
    "src/dartwing_ocr/pipeline/",
)

# Strings forbidden by FR-030 (line-item extraction is explicitly OUT
# of stage 1 MVP scope — see spec.md "Out of Scope" + FR-030).
_FR030_FORBIDDEN_STRINGS: tuple[str, ...] = (
    "line_item",
    "line-item",
    "line items",
    "extract_lines",
)


# ---------------------------------------------------------------------------
# Check 1 — smoke imports of feature 019 + feature 021 public surfaces
# ---------------------------------------------------------------------------


def test_feature_019_ocr_only_module_imports() -> None:
    """Feature 019 OCR-only fast lane module imports cleanly.

    Imports the public module, NOT any function — even a stale import
    chain would trip this. The module is part of the preprocessing
    subtree, so it MUST exist unchanged at landing.

    The feature-019 module transitively imports ``PIL`` / ``numpy``; we
    skip cleanly if those are not installed in the test env (CPU-only
    CI without Pillow). The git-history regression check below is the
    canonical guarantee — importing the module is just a sanity
    cross-check.
    """
    pytest.importorskip("PIL")
    pytest.importorskip("numpy")
    import importlib

    mod = importlib.import_module("dartwing_ocr.preprocessing.ocr_only")
    # Confirm the module loaded from the expected location (catches a
    # silently-shadowed module).
    assert mod.__file__ is not None
    assert "preprocessing/ocr_only.py" in mod.__file__.replace("\\", "/")


def test_feature_021_pipeline_runner_module_imports() -> None:
    """Feature 021 GPU-MVP pipeline runner module imports cleanly.

    The runner lives at ``dartwing_ocr.pipeline.runner`` (feature 011
    runtime profiles + feature 021 GPU MVP promotion). Importing it
    confirms the full pipeline subtree is reachable without a Paddle
    import side-effect — feature 022 must not have wedged a circular
    or paddle-import-on-load dependency in.
    """
    import importlib

    mod = importlib.import_module("dartwing_ocr.pipeline.runner")
    assert mod.__file__ is not None
    assert "pipeline/runner.py" in mod.__file__.replace("\\", "/")


def test_feature_020_evidence_gate_module_imports() -> None:
    """Feature 020 vendor-identity evidence-gate module imports cleanly.

    Feature 022's gate-side code reuses ``Y_THRESHOLD_FRACTION`` from
    this module (the constant is bound locally in
    ``preprocessing.evidence_gate`` and re-exported in
    ``dartwing_ocr.evaluator.semantic_quality_body_ocr`` as
    ``EVIDENCE_GATE_Y_THRESHOLD_FRACTION`` per MI-7) — so a regression
    here would surface immediately at gate-time as well. This is a
    cross-check that the
    canonical import path stays valid.
    """
    import importlib

    mod = importlib.import_module("dartwing_ocr.preprocessing.evidence_gate")
    # The constant is called ``Y_THRESHOLD_FRACTION`` (no
    # ``EVIDENCE_GATE_`` prefix at the call site — the module name
    # provides the namespace). Feature 022's gate-side body OCR helper
    # imports this symbol per MI-7 / R-022.4.
    assert hasattr(mod, "Y_THRESHOLD_FRACTION")
    # Pin the value at 0.25 — feature 022 reuses this exact threshold.
    # Floats compared via pytest.approx (Sonar python:S1244).
    assert mod.Y_THRESHOLD_FRACTION == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Check 2 — git history shows no protected-subtree edits by feature 022
# ---------------------------------------------------------------------------


def _git_merge_base_with_main() -> str:
    """Return the merge-base commit SHA between HEAD and origin/main.

    Falls back to ``main`` (local) when ``origin/main`` is not configured
    (e.g. in CI checkout without remotes). Raises ``RuntimeError`` if
    neither resolves — that is a real CI misconfiguration, not a test
    smell.
    """
    for ref in ("origin/main", "main"):
        # NOSONAR: local git command, args are static literals, no shell injection surface
        result = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    raise RuntimeError("could not resolve merge-base with main")


def _files_changed_since(base_sha: str) -> set[str]:
    """Return the set of repo-relative file paths changed between
    ``base_sha`` and ``HEAD`` (Added or Modified)."""
    # NOSONAR: local git command, args are static literals, no shell injection surface
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}..HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_no_protected_subtree_files_changed_by_feature_022() -> None:
    """No file under the five protected pipeline subtrees may appear in
    the git diff between the feature branch and its merge-base with main.

    This is the FR-021 / FR-022 / FR-023 / FR-028 enforcement gate at the
    repository level — stronger than a behavioral test because it catches
    even no-op edits (whitespace, docstring rewording, import reorder)
    that the constitution forbids feature 022 from making.

    The check skips with a clear reason if the git merge-base cannot be
    resolved (e.g. a shallow CI checkout without ``main``) — failing
    spuriously on a CI infra issue would be worse than the gap.
    """
    # Per Codex P2 review on PR #49 (2026-05-24): a CI environment that
    # can't resolve origin/main OR main is a real misconfiguration that
    # should FAIL the gate, not silently skip — otherwise FR-021/MI-22
    # protected-subtree checks are dead in those environments. Only
    # legitimate environment-skip path is the explicit RuntimeError from
    # the resolver, which we let propagate as the test failure.
    base = _git_merge_base_with_main()

    changed = _files_changed_since(base)
    violations: list[str] = []
    for path in sorted(changed):
        for protected in _PROTECTED_SUBTREES:
            if path.startswith(protected):
                violations.append(path)
                break

    assert not violations, (
        "feature 022 modified files under protected pipeline subtrees — "
        "FR-021/FR-022/FR-023/FR-028/MI-22 violation:\n  "
        + "\n  ".join(violations)
    )


# ---------------------------------------------------------------------------
# Check 3 — FR-030 negative grep + line-item-absence in contracts
# ---------------------------------------------------------------------------


# Allowlist: pre-existing matches (e.g. in code or docs that predate
# feature 022) are recorded here by SHA-256 of the line containing the
# match (stripped of leading/trailing whitespace), so the test ignores
# stable historical content. ANY new line containing one of the
# forbidden strings would have a different hash and fail the test.
#
# Two pre-existing matches live in ``src/dartwing_ocr/preprocessing/ocr.py``:
# a private helper ``_extract_lines(...)`` that converts PaddleOCR raw
# output into ``LineCandidate`` records — this is preprocessing
# infrastructure, NOT line-item extraction. The function shares a name
# with the forbidden string ``extract_lines`` purely by coincidence
# (PaddleOCR uses "line" to mean a horizontal text strip, not a table
# line-item). Both hashes are pinned here.
# Per Codex P2 + Copilot review on PR #49 (2026-05-24): scope the
# allowlist by (repo-relative path, sha256(stripped-line)) tuple rather
# than by line-hash alone. Hash-alone allowlisting would auto-suppress a
# NEW violation if the same stripped text happens to appear in a
# different file. Path-scoped tuples force any new occurrence in a new
# location to be re-adjudicated.
_FR030_LINE_HASH_ALLOWLIST: frozenset[tuple[str, str]] = frozenset(
    {
        # src/dartwing_ocr/preprocessing/ocr.py:385 — `def _extract_lines(`
        # Hash = sha256(stripped-line) — kept identical to the pre-PR-49
        # bare-hash form so the change is purely a key-tuple expansion.
        (
            "src/dartwing_ocr/preprocessing/ocr.py",
            "e1b05a303d123ede79fa8aa7c71d15c56a94a0ed00d086c0544218359c77ad25",
        ),
        # src/dartwing_ocr/preprocessing/ocr.py:680 — call site
        (
            "src/dartwing_ocr/preprocessing/ocr.py",
            "daec13bbe99041c0bfc8f8b2545ae2b691c33e5ef146dff15dfb2cbed14aa799",
        ),
    }
)


@functools.lru_cache(maxsize=1)
def _iter_source_lines() -> tuple[tuple[Path, int, str], ...]:
    """Return ``(path, lineno, line)`` triples for every ``.py`` file
    under ``src/dartwing_ocr/``. Trims newline; preserves leading
    whitespace.

    Cached per-process via ``@lru_cache(maxsize=1)`` so the parametrized
    FR-030 test (which iterates 4 forbidden strings) re-uses the same
    file walk instead of re-reading every .py file four times. Per
    Copilot review on PR #49 (2026-05-24) — perf nit.
    """
    out: list[tuple[Path, int, str]] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        # Skip __pycache__ entirely (defensive — rglob already excludes
        # compiled artifacts, but a stale .py inside a cache dir would
        # not).
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            out.append((path, lineno, line))
    return tuple(out)


def _hash_line(line: str) -> str:
    """SHA-256 of the line's UTF-8 bytes (no leading/trailing whitespace
    normalized so allowlist hashes are stable across formatting tweaks)."""
    return hashlib.sha256(line.strip().encode("utf-8")).hexdigest()


def _rel_path(path: Path) -> str:
    """Return the repo-relative POSIX path string for ``path``.

    Used for the path-scoped FR-030 allowlist lookup (Codex P2 PR #49
    2026-05-24) — every (path, hash) tuple is compared with this
    canonical key form.
    """
    return path.relative_to(REPO_ROOT).as_posix()


@pytest.mark.parametrize("forbidden", _FR030_FORBIDDEN_STRINGS)
def test_fr030_no_line_item_strings_in_src(forbidden: str) -> None:
    """FR-030: feature 022 evaluates table quality but MUST NOT introduce
    line-item EXTRACTION code. Grep ``src/dartwing_ocr/`` for the four
    line-item-related strings and assert zero non-allowlisted matches.

    Uses a case-sensitive search — ``Line_Item`` / ``LineItem`` are
    different concepts the gate may legitimately mention in passing
    docstrings. Adjust the allowlist (above) if pre-existing matches
    appear; do NOT weaken the forbidden list.

    Allowlist lookup is (path, hash)-scoped (Codex P2 PR #49 2026-05-24
    — hash-alone allowlisting would auto-suppress a NEW violation if
    the same stripped text appears in a different file).
    """
    pattern = re.compile(re.escape(forbidden))
    new_violations: list[str] = []
    for path, lineno, line in _iter_source_lines():
        if pattern.search(line):
            key = (_rel_path(path), _hash_line(line))
            if key in _FR030_LINE_HASH_ALLOWLIST:
                continue
            rel = path.relative_to(REPO_ROOT)
            new_violations.append(f"{rel}:{lineno}: {line.strip()}")

    assert not new_violations, (
        "FR-030 violation — found forbidden line-item string "
        f"{forbidden!r} in src/dartwing_ocr/:\n  "
        + "\n  ".join(new_violations)
        + "\n\nIf this match is a pre-existing line that predates "
        "feature 022, add its (rel_path, sha256) tuple to "
        "_FR030_LINE_HASH_ALLOWLIST."
    )


def test_fr030_no_line_items_property_in_v1_3_schemas() -> None:
    """FR-030: no v1.3.0 contract schema may declare a ``line_items``
    property. Iterate every ``*.schema.json`` under v1.3.0 and assert
    none of them contains ``"line_items"`` as a JSON object key.

    We walk the parsed JSON tree (not a regex grep) so docstrings
    mentioning "line items" in a description string do not trip the
    test — only structural property keys matter for the contract.
    """
    contracts_dir = REPO_ROOT / "contracts" / "stage1_vendor_identity" / "v1.3.0"
    offenders: list[str] = []
    for schema_path in sorted(contracts_dir.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if _json_has_object_key(schema, "line_items"):
            offenders.append(schema_path.name)

    assert not offenders, (
        f"FR-030 violation — v1.3.0 contract schema(s) declare a "
        f"`line_items` property: {offenders}"
    )


def _json_has_object_key(node: object, target: str) -> bool:
    """Return True iff ``node`` (or any nested dict/list) contains an
    object key equal to ``target``. Cognitive complexity intentionally
    low (single recursion, single conditional)."""
    if isinstance(node, dict):
        if target in node:
            return True
        return any(_json_has_object_key(v, target) for v in node.values())
    if isinstance(node, list):
        return any(_json_has_object_key(item, target) for item in node)
    return False


def test_fr030_final_structured_payload_schema_byte_identical_v1_2_to_v1_3() -> None:
    """FR-030 / MI-22: ``final_structured_payload.schema.json`` is byte-
    identical (SHA-256 match) between v1.2.0 and v1.3.0. Confirms feature
    022 added no field — line-item or otherwise — to the final
    downstream payload contract.
    """
    contracts = REPO_ROOT / "contracts" / "stage1_vendor_identity"
    v1_2 = contracts / "v1.2.0" / "final_structured_payload.schema.json"
    v1_3 = contracts / "v1.3.0" / "final_structured_payload.schema.json"
    assert v1_2.is_file(), f"missing v1.2.0 schema: {v1_2}"
    assert v1_3.is_file(), f"missing v1.3.0 schema: {v1_3}"

    h1 = hashlib.sha256(v1_2.read_bytes()).hexdigest()
    h2 = hashlib.sha256(v1_3.read_bytes()).hexdigest()
    assert h1 == h2, (
        f"FR-030 / MI-22 violation — final_structured_payload.schema.json "
        f"diverged between v1.2.0 ({h1}) and v1.3.0 ({h2}); feature 022 "
        f"must not modify this contract."
    )


def test_fr030_expected_schema_byte_identical_v1_2_to_v1_3() -> None:
    """FR-006 / MI-23: ``expected.json`` retains its v1.2.0 shape. We
    enforce by SHA-256 byte-identity between the v1.2.0 and v1.3.0
    schema files. Cross-checks T014's identical assertion at the US4
    layer."""
    contracts = REPO_ROOT / "contracts" / "stage1_vendor_identity"
    v1_2 = contracts / "v1.2.0" / "expected.schema.json"
    v1_3 = contracts / "v1.3.0" / "expected.schema.json"
    h1 = hashlib.sha256(v1_2.read_bytes()).hexdigest()
    h2 = hashlib.sha256(v1_3.read_bytes()).hexdigest()
    assert h1 == h2, (
        f"FR-006 / MI-23 violation — expected.schema.json diverged "
        f"between v1.2.0 ({h1}) and v1.3.0 ({h2}); feature 022 must not "
        f"alter the expected.json contract."
    )
