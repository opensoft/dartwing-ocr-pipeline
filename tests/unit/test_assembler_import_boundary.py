"""T053 — FR-023/FR-025: assembler must be pure, artifact-to-artifact.

Statically inspects every module under src/dartwing_ocr/assembler/ and
asserts none of them import preprocessing, pipeline code, model clients,
or network libraries.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ASSEMBLER_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "dartwing_ocr"
    / "assembler"
)

FORBIDDEN_PREFIXES = (
    "dartwing_ocr.preprocessing",
    "dartwing_ocr.pipeline",
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "socket",
    "http.client",
    "aiohttp",
    "ollama",
    "openai",
    "anthropic",
    "google.generativeai",
    "transformers",
    "torch",
    "paddleocr",
    "paddle",
)


def _collect_imports(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative imports inside the assembler package are fine
            if node.module:
                names.append(node.module)
    return names


def _forbidden(name: str) -> str | None:
    for prefix in FORBIDDEN_PREFIXES:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


def _assembler_modules() -> list[Path]:
    return sorted(p for p in ASSEMBLER_ROOT.rglob("*.py"))


def test_assembler_package_exists():
    assert ASSEMBLER_ROOT.is_dir()
    assert _assembler_modules(), "expected at least one module under assembler/"


@pytest.mark.parametrize("module_path", _assembler_modules(), ids=lambda p: p.name)
def test_no_forbidden_imports(module_path: Path):
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    for name in _collect_imports(tree):
        hit = _forbidden(name)
        assert hit is None, (
            f"{module_path.relative_to(ASSEMBLER_ROOT)} imports forbidden "
            f"module '{name}' (matched prefix '{hit}'). The assembler must be "
            f"a pure artifact-to-artifact transform."
        )
