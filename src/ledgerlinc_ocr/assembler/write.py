"""Deterministic JSON writer for `final_structured_payload.json` (research Decision 1)."""

from __future__ import annotations

import json
from pathlib import Path

FINAL_KEY_ORDER = [
    "contract_set_version",
    "pipeline_version",
    "document_id",
    "processed_at",
    "document_type",
    "vendor_candidate",
    "review_status",
    "quality_summary",
    "trace",
]


def _ordered_top_level(payload: dict) -> dict:
    """Return a new dict with top-level keys in FINAL_KEY_ORDER, preserving sub-dict order."""
    ordered: dict = {}
    for key in FINAL_KEY_ORDER:
        if key in payload:
            ordered[key] = payload[key]
    for key in payload:
        if key not in ordered:
            ordered[key] = payload[key]
    return ordered


def write_final_payload(path: Path, payload: dict) -> None:
    """Write `payload` to `path` deterministically: UTF-8, indent=2, trailing newline."""
    ordered = _ordered_top_level(payload)
    text = json.dumps(
        ordered,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
        sort_keys=False,
    )
    path.write_text(text + "\n", encoding="utf-8")
