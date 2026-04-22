"""Deterministic JSON read/write helpers per research.md §10."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read JSON from `path` using UTF-8. Raises FileNotFoundError if absent."""
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def round_floats(obj: Any, ndigits: int = 6) -> Any:
    """Recursively round every float in `obj` to `ndigits` decimals."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v, ndigits) for v in obj]
    if isinstance(obj, tuple):
        return tuple(round_floats(v, ndigits) for v in obj)
    return obj


def serialize(obj: Any) -> str:
    """Serialize `obj` to a deterministic JSON string with trailing newline."""
    rounded = round_floats(obj)
    return (
        json.dumps(
            rounded,
            indent=2,
            ensure_ascii=False,
            separators=(",", ": "),
            sort_keys=False,
        )
        + "\n"
    )


def write_json(path: Path, obj: Any) -> None:
    """Write `obj` to `path` as deterministic UTF-8 JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = serialize(obj)
    path.write_text(text, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Write `text` to `path` as UTF-8 with exactly one trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text = text + "\n"
    path.write_text(text, encoding="utf-8")
