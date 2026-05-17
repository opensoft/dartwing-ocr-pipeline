"""Feature 020 / T045 / FR-014 / MI-4 / MI-5: CPU-isolation static check.

Asserts that none of the feature 020 CPU code paths (gate body + opt-in
helper + pipeline disposition seam) imports any GPU-only module at
module load. The contract is:

- ``preprocessing/evidence_gate.py`` — pure-function gate body; only
  ``re`` / ``statistics`` / ``unicodedata`` / ``dataclasses`` /
  ``typing`` / ``preprocessing.identifiers`` permitted at module level
  (per the MVP test ``test_evidence_gate_module_safety_unit.py`` which
  pinned this for US1).

- ``preprocessing/evidence_gate_optin.py`` — CLI/env-var resolver +
  warn-message helper; only ``os`` / ``typing`` permitted at module
  level (mirrors ``preprocess_strategy_optin.py`` / etc.).

- Neither module pulls in GPU-only modules from feature 019's
  preprocess-strategy machinery (``preprocessing.ocr_only``,
  ``preprocessing.warmup``, ``preprocessing.ocr``, etc.) — those
  modules in turn import PaddleOCR and would break a no-Paddle CPU
  host's import graph.

CPU-safe by construction — this file uses static source inspection
(grep-style needles applied to the module source text) and does NOT
import the heavy modules being audited. It is the same pattern as the
MVP test ``test_evidence_gate_module_safety_unit.py``.

The test fails if any future regression silently adds a GPU-only or
Paddle import to the two CPU surfaces.
"""

from __future__ import annotations

import importlib
import importlib.util
from typing import Iterable

# Feature 019 GPU-only / Paddle-tainted modules that the feature 020
# CPU surface MUST NOT import at module load. Sourced from:
#
#   - ``preprocessing.ocr`` — imports paddleocr.PaddleOCR
#   - ``preprocessing.ocr_only`` — imports paddleocr.PaddleOCR via ocr
#   - ``preprocessing.warmup`` — imports paddleocr / MIOpen probes
#   - ``preprocessing.preflight`` — imports paddle to probe GPU
#   - ``preprocessing.pipeline`` — orchestrator; lazily imports paddle
#   - ``preprocessing.rasterize`` — imports pypdfium2 (acceptable in
#     CLI but not in pure CPU helpers)
#
# This list is the contract: any addition to feature 020's CPU
# surface that imports one of these breaks FR-014.
_GPU_TAINTED_MODULE_NEEDLES: tuple[str, ...] = (
    # Project-internal module-name needles. The full package prefix
    # `ledgerlinc_ocr.preprocessing.` is REQUIRED — every internal
    # import in `src/ledgerlinc_ocr/preprocessing/*.py` uses the fully-
    # qualified form, so substring-matching the bare `preprocessing.X`
    # never fires on a regression. The prefix-qualified form is the
    # canonical regression vector and the only form the test scan can
    # catch.
    "ledgerlinc_ocr.preprocessing.ocr",
    "ledgerlinc_ocr.preprocessing.ocr_only",
    "ledgerlinc_ocr.preprocessing.warmup",
    "ledgerlinc_ocr.preprocessing.preflight",
    "ledgerlinc_ocr.preprocessing.pipeline",
    "ledgerlinc_ocr.preprocessing.rasterize",
    # Third-party GPU/ML stack — anything from these is forbidden in a
    # CPU-only helper module.
    "paddleocr",
    "paddlepaddle",
    "pypdfium2",
    "PIL",
    "numpy",
    "torch",
    "tensorflow",
)


def _module_source(module_name: str) -> str:
    """Read the source text of a module without triggering its imports
    of OTHER modules (we only need to scan the source file)."""
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"module {module_name!r} not found on sys.path"
    assert spec.origin is not None, f"module {module_name!r} has no source file"
    with open(spec.origin, encoding="utf-8") as f:
        return f.read()


def _forbidden_import_needles(needle: str) -> Iterable[str]:
    """Generate the grep needles that catch a forbidden import of ``needle``
    in both ``import X`` and ``from X import …`` forms. Conservative on
    purpose — a few extra checks cost nothing and pin the contract
    tighter than a single regex would."""
    return (
        f"import {needle}\n",
        f"import {needle} ",
        f"from {needle} ",
        f"from {needle}.",
        f"from {needle} import",
    )


# ---------------------------------------------------------------------------
# T045 — preprocessing.evidence_gate is CPU-isolated.
# ---------------------------------------------------------------------------


def test_evidence_gate_has_no_gpu_tainted_imports() -> None:
    """Static source scan of ``preprocessing/evidence_gate.py``: NO line
    may import any module from the GPU-tainted list at module level
    (FR-014 / MI-4 / MI-5)."""
    src = _module_source("ledgerlinc_ocr.preprocessing.evidence_gate")
    # Strip docstrings/comments-with-needles by line-prefix filtering.
    # Imports are at the top of the file, never inside docstrings —
    # but for defensive robustness, only inspect non-comment lines.
    code_lines = [
        line
        for line in src.splitlines()
        if not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines) + "\n"
    for needle in _GPU_TAINTED_MODULE_NEEDLES:
        for forbidden in _forbidden_import_needles(needle):
            assert forbidden not in code, (
                f"preprocessing/evidence_gate.py contains a forbidden "
                f"GPU-tainted import: {forbidden!r} (FR-014 / MI-4 / MI-5)"
            )


# ---------------------------------------------------------------------------
# T045 — preprocessing.evidence_gate_optin is CPU-isolated.
# ---------------------------------------------------------------------------


def test_evidence_gate_optin_has_no_gpu_tainted_imports() -> None:
    """Static source scan of ``preprocessing/evidence_gate_optin.py``:
    NO line may import any module from the GPU-tainted list at module
    level (FR-014 / MI-4 / MI-5)."""
    src = _module_source("ledgerlinc_ocr.preprocessing.evidence_gate_optin")
    code_lines = [
        line
        for line in src.splitlines()
        if not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines) + "\n"
    for needle in _GPU_TAINTED_MODULE_NEEDLES:
        for forbidden in _forbidden_import_needles(needle):
            assert forbidden not in code, (
                f"preprocessing/evidence_gate_optin.py contains a forbidden "
                f"GPU-tainted import: {forbidden!r} (FR-014 / MI-4 / MI-5)"
            )


# ---------------------------------------------------------------------------
# T045 — Sanity: both modules import successfully on this CPU host.
# (Paddle may be installed in the venv for OTHER reasons but neither
# of our modules should trigger its load. This is a smoke test only —
# the strong invariant is the static source check above; this is a
# defense-in-depth.)
# ---------------------------------------------------------------------------


def test_evidence_gate_and_optin_import_cleanly() -> None:
    """Both CPU helper modules import on a no-Paddle host. (The MVP
    test ``test_evidence_gate_module_safety_unit.py`` already covers
    the gate body; this widens coverage to the opt-in helper which
    landed in US4.)"""
    import ledgerlinc_ocr.preprocessing.evidence_gate as gate
    import ledgerlinc_ocr.preprocessing.evidence_gate_optin as gate_optin

    assert gate is not None
    assert gate_optin is not None
    # Spot-check the public APIs that the CLI relies on are present —
    # a refactor that hid them behind a GPU-only conditional would
    # break the import-clean property and ALSO break the CLI on CPU.
    assert hasattr(gate, "evaluate_evidence_gate")
    assert hasattr(gate, "should_suppress_fallback")
    assert hasattr(gate_optin, "resolve_evidence_gate_skip_fallback")
    assert hasattr(gate_optin, "evidence_gate_skip_fallback_warn_message")
    assert hasattr(gate_optin, "EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR")


# ---------------------------------------------------------------------------
# T045 — Sanity: stdlib-only top-level imports on both files.
# Tracks the explicit allow-list documented in the module docstrings.
# ---------------------------------------------------------------------------


_ALLOWED_IMPORT_PREFIXES: tuple[str, ...] = (
    "re",
    "statistics",
    "unicodedata",
    "dataclasses",
    "typing",
    "os",
    "collections.abc",
    "ledgerlinc_ocr.preprocessing.identifiers",
)


def _collect_top_level_imports(src: str) -> list[str]:
    """Extract module names from top-level ``import X`` /
    ``from X import …`` lines. Skips lines inside functions (indented)
    so lazy imports do NOT count as module-level."""
    names: list[str] = []
    for line in src.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Top-level only — indented lines are inside functions/methods.
        if line[0] in (" ", "\t"):
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("from __future__ "):
            continue
        if stripped.startswith("import "):
            # `import X` or `import X as Y` or `import X, Y`
            payload = stripped[len("import ") :]
            for part in payload.split(","):
                names.append(part.strip().split(" as ")[0].split(".")[0])
        elif stripped.startswith("from "):
            # `from X import …`
            payload = stripped[len("from ") :]
            module = payload.split(" import ", 1)[0].strip()
            names.append(module)
    return names


def _assert_imports_in_allowed_set(module_name: str) -> None:
    """Top-level imports must all match one of the allowed prefixes."""
    src = _module_source(module_name)
    imports = _collect_top_level_imports(src)
    for name in imports:
        ok = any(
            name == allowed or name.startswith(allowed + ".")
            for allowed in _ALLOWED_IMPORT_PREFIXES
        )
        assert ok, (
            f"{module_name} imports {name!r} at module level, which is "
            f"not in the CPU-safe allow-list "
            f"({sorted(_ALLOWED_IMPORT_PREFIXES)}) — FR-014 / MI-4 / MI-5"
        )


def test_evidence_gate_top_level_imports_are_stdlib_only() -> None:
    """Top-level imports of evidence_gate.py are all in the CPU-safe
    allow-list (stdlib + ``preprocessing.identifiers``)."""
    _assert_imports_in_allowed_set("ledgerlinc_ocr.preprocessing.evidence_gate")


def test_evidence_gate_optin_top_level_imports_are_stdlib_only() -> None:
    """Top-level imports of evidence_gate_optin.py are all in the
    CPU-safe allow-list (stdlib only)."""
    _assert_imports_in_allowed_set(
        "ledgerlinc_ocr.preprocessing.evidence_gate_optin"
    )
