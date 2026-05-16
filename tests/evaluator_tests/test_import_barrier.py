"""Constitution §I — the evaluator (harness-side) must not import from the
pipeline or preprocessing subpackages. Enforced at the source-code level via
AST scan so the barrier holds even for modules that are lazy-imported or only
reached on rare code paths."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_EVALUATOR_SRC = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "dartwing_ocr"
    / "evaluator"
)
_FORBIDDEN_PREFIXES = (
    "dartwing_ocr.pipeline",
    "dartwing_ocr.preprocessing",
)


def _forbidden_imports(tree: ast.AST) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_FORBIDDEN_PREFIXES):
                    hits.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith(_FORBIDDEN_PREFIXES):
                hits.append(mod)
    return hits


@pytest.mark.parametrize(
    "py_file", sorted(_EVALUATOR_SRC.rglob("*.py")), ids=lambda p: p.name
)
def test_no_pipeline_or_preprocessing_imports(py_file: Path) -> None:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    violations = _forbidden_imports(tree)
    assert not violations, (
        f"{py_file.relative_to(_EVALUATOR_SRC.parents[2])} violates "
        f"Constitution §I (harness/pipeline boundary): imports {violations}"
    )
