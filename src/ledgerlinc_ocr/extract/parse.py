"""Model-response parser with a minimal JSON repair pipeline (R-007).

Strict `json.loads` first. On failure, apply up to three deterministic repair
steps (strip BOM, strip markdown fences, strip leading/trailing prose) and
re-attempt. Every step that fires is recorded in the repair trail, which the
reconciler surfaces as a `warnings` entry and downgrades `status` to
`"partial"`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .errors import UnrepairableResponse

_BOM = "﻿"
_FENCE_RE = re.compile(r"^```(?:json|JSON)?\s*\n(.*?)\n```\s*$", re.DOTALL)
_LEADING_JSON_RE = re.compile(r"(?P<json>[\[{].*[\]}])", re.DOTALL)


def _strip_bom(text: str) -> tuple[str, bool]:
    if text.startswith(_BOM):
        return text.lstrip(_BOM), True
    return text, False


def _strip_markdown_fence(text: str) -> tuple[str, bool]:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1), True
    return text, False


def _strip_prose(text: str) -> tuple[str, bool]:
    """Pull out the first `{...}` or `[...]` block (greedy to the final brace)."""

    match = _LEADING_JSON_RE.search(text)
    if match and match.group("json") != text.strip():
        return match.group("json"), True
    return text, False


def parse_model_response(raw_body: str) -> tuple[dict, list[str]]:
    """Parse a voter's raw body string into a dict + repair trail.

    Raises `UnrepairableResponse` when both the strict and repaired attempts
    fail.
    """

    repair_trail: list[str] = []
    body = raw_body

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        first_error = exc
    else:
        if not isinstance(parsed, dict):
            raise UnrepairableResponse(
                "model response is valid JSON but not an object",
                detail={"received_type": type(parsed).__name__},
            )
        return parsed, repair_trail

    body, stripped = _strip_bom(body)
    if stripped:
        repair_trail.append("stripped BOM")

    body, stripped = _strip_markdown_fence(body)
    if stripped:
        repair_trail.append("stripped markdown code fence")

    body, stripped = _strip_prose(body)
    if stripped:
        repair_trail.append("stripped leading/trailing prose")

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise UnrepairableResponse(
            "model response is not valid JSON and minimal repair failed",
            detail={
                "first_error": str(first_error),
                "second_error": str(exc),
                "repair_trail": list(repair_trail),
            },
        ) from exc

    if not isinstance(parsed, dict):
        raise UnrepairableResponse(
            "model response repaired but is not a JSON object",
            detail={"received_type": type(parsed).__name__},
        )

    return parsed, repair_trail
