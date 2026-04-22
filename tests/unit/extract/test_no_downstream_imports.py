"""T093 / analysis C5 — FR-020/FR-021: module-boundary enforcement.

Walk `src/ledgerlinc_ocr/extract/**/*.py` and assert no import references a
banned downstream module (routing, consensus, final_payload, evaluation), a
cloud-provider SDK (boto3, google.cloud, azure.ai), or the `requests` HTTP
library (R-001 pins the extractor to `httpx`).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXTRACT_ROOT = _REPO_ROOT / "src" / "ledgerlinc_ocr" / "extract"

_BANNED_PREFIXES = (
    "routing",
    "consensus",
    "final_payload",
    "evaluation",
    "boto3",
    "google.cloud",
    "azure.ai",
    "requests",
)


def _iter_modules() -> list[Path]:
    return [
        p for p in _EXTRACT_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


def _matches_banned(module_name: str) -> str | None:
    for prefix in _BANNED_PREFIXES:
        if module_name == prefix or module_name.startswith(prefix + "."):
            return prefix
    return None


def test_no_banned_imports_under_extract() -> None:
    violations: list[tuple[Path, int, str]] = []
    modules = _iter_modules()
    assert modules, f"no modules found under {_EXTRACT_ROOT}"

    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    hit = _matches_banned(alias.name)
                    if hit:
                        violations.append((path, node.lineno, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                hit = _matches_banned(mod)
                if hit:
                    violations.append((path, node.lineno, f"from {mod} import ..."))

    assert not violations, (
        "banned imports under src/ledgerlinc_ocr/extract/:\n"
        + "\n".join(f"  {p.relative_to(_REPO_ROOT)}:{ln}  {msg}" for p, ln, msg in violations)
    )
