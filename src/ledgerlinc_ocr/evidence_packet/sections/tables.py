"""Tables: verbatim passthrough (FR-006). No re-interpretation."""
from __future__ import annotations

from typing import Any


def build_tables_section(preprocess_output: dict[str, Any]) -> list[dict[str, Any]]:
    return list(preprocess_output["tables"])
