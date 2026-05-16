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
    """Write `payload` to `path` deterministically: UTF-8, indent=2, trailing newline.

    Path-injection note (Sonar pythonsecurity:S2083): this function trusts
    the caller. `pipeline/path_resolution.py::resolve_destination` only
    normalizes via `.expanduser().resolve()` — it does NOT reject `..`
    traversals, symlinks, or absolute escapes. The pipeline CLI is the
    trust boundary: it accepts `--input` / `--document-folder` /
    `--output-dir` from the operator, and the operator is assumed to be
    running the CLI in their own session against their own filesystem.
    Library callers (e.g., tests, downstream tools) that wire untrusted
    paths into this function MUST validate the path themselves —
    typically by anchoring it under a known-safe root via
    `Path.is_relative_to(...)`.
    """
    ordered = _ordered_top_level(payload)
    text = json.dumps(
        ordered,
        ensure_ascii=False,
        indent=2,
        separators=(",", ": "),
        sort_keys=False,
    )
    path.write_text(text + "\n", encoding="utf-8")  # NOSONAR pythonsecurity:S2083 — caller-trusts-path contract; see docstring.
